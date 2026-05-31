#!/usr/bin/env python3
"""
策划工具箱 — PyInstaller 打包脚本 + 更新服务器文件生成

用法:
  cd toolbox_core
  python build.py

输出:
  dist/策划工具箱/          ← 可分发目录
  update-server/version.json  ← 版本信息（供客户端检查更新）
  update-server/策划工具箱_v1.0.zip  ← 更新包（可选，加 --zip）

参数:
  --zip  同时生成 update-server 下的更新 zip 包

环境:
  需要先 pip install pyinstaller
  当前电脑上运行一次后得到 dist/，即可整个目录分发给用户
"""
import os
import sys
import json
import shutil
import subprocess
import hashlib
import zipfile
import time
from datetime import datetime

WORKSPACE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CORE_DIR = os.path.join(WORKSPACE, "toolbox_core")
DIST_DIR = os.path.join(WORKSPACE, "dist")
UPDATE_DIR = os.path.join(WORKSPACE, "update-server")
APP_NAME = "策划工具箱"

# 从 update_version.py 读取版本号（唯一来源）
_ver_line = [l for l in open(os.path.join(CORE_DIR, "update_version.py"), encoding="utf-8") if "APP_VERSION" in l and "=" in l]
APP_VERSION = _ver_line[0].split("=", 1)[1].strip().strip('"').strip("'") if _ver_line else "v1.0"

# PV_HOST = "192.168.1.41"  # 你的开发机 IP，发给用户前改成实际地址
# UPDATE_URL 在 update_version.py 中配置，打包时自动读取

# ── 需要打包的核心 Python 文件 ──
CORE_SCRIPTS = [
    "desktop_main.py",
    "web_app.py",
    "svn_oneclick_compare.py",
    "toolbox_config.py",
    "toolbox_platform.py",
    "toolbox_merge.py",
    "xlsm_zipper.py",
    "export_error_code.py",
    "update_version.py",
    "lang_map.txt",
]

# ── 子进程调用的 worker 脚本（PyInstaller 不会自动追踪，需手动加入）──
WORKER_SCRIPTS = [
    "_cmp_worker.py",
    "_merge_analyzer.py",
    "_merge_analyze_worker.py",
    "_export_error_code_erl.py",
]

# ── Flask 模板/静态文件 ──
DATA_DIRS = [
    ("templates", "templates"),
    ("assets", "assets"),
    ("splash", "splash"),
]

# ── 更新器辅助脚本 ──
UPDATER_SCRIPT = "_updater.bat"


def _get_pyinstaller():
    pyi = shutil.which("pyinstaller")
    if pyi:
        return pyi
    candidates = [
        os.path.join(os.path.dirname(sys.executable), "pyinstaller.exe"),
        os.path.join(os.path.dirname(sys.executable), "Scripts", "pyinstaller.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _ensure_worker_scripts():
    """检查 worker 脚本是否存在（只报错不复制，不影响本地工程）"""
    missing = []
    for name in WORKER_SCRIPTS:
        src = os.path.join(WORKSPACE, name)
        if not os.path.isfile(src):
            missing.append(name)
    if missing:
        print(f"  [警告] worker 脚本不存在: {', '.join(missing)}")
    return []


def _cleanup_copied_workers(copied):
    pass


def _strip_api_key():
    """读取配置，去掉 API Key"""
    config_path = os.path.join(CORE_DIR, "svn_gui_config.json")
    if not os.path.isfile(config_path):
        print("  [跳过] config 文件不存在")
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    removed = []
    if "tr_api_key_enc" in cfg:
        del cfg["tr_api_key_enc"]
        removed.append("tr_api_key_enc")
    if "tr_api_key" in cfg:
        del cfg["tr_api_key"]
        removed.append("tr_api_key")
    if removed:
        print(f"  [清理] 已移除 API Key 字段: {', '.join(removed)}")
    return cfg


def _get_data_args():
    """生成 PyInstaller --add-data 参数列表"""
    args = []
    for src_rel, dst_rel in DATA_DIRS:
        src = os.path.join(CORE_DIR, src_rel)
        if os.path.exists(src):
            args.append(f"--add-data={src};{dst_rel}")
            print(f"  [数据] {src_rel}/ → {dst_rel}/")
    for name in WORKER_SCRIPTS:
        src = os.path.join(WORKSPACE, name)
        if os.path.isfile(src):
            args.append(f"--add-data={src};.")
            print(f"  [数据] {name} → ./")
    updater = os.path.join(CORE_DIR, UPDATER_SCRIPT)
    if os.path.isfile(updater):
        args.append(f"--add-data={updater};.")
        print(f"  [数据] {UPDATER_SCRIPT} → ./")
    return args


def _get_hidden_imports():
    """解决 PyInstaller 自动检测不到的依赖"""
    return [
        "--hidden-import=win32timezone",
        "--hidden-import=cffi",
        "--hidden-import=pycparser",
    ]


def _get_path_args():
    """添加 PyInstaller 模块搜索路径（main.py 中 sys.path.insert 出来的路径）"""
    return [
        "--paths", CORE_DIR,
    ]


def _deploy_to_appdata(dist_app):
    """部署到 %APPDATA%/planning-toolbox/ 固定路径，使托盘设置不丢失"""
    appdata_dir = os.environ.get("APPDATA", os.path.expanduser("~"))
    deploy_root = os.path.join(appdata_dir, "planning-toolbox")
    deploy_dir = os.path.join(deploy_root, APP_NAME)
    deploy_exe = os.path.join(deploy_dir, f"{APP_NAME}.exe")

    print(f"\n{'='*60}")
    print("  Step 9: 部署到 APPDATA")
    print(f"{'='*60}")

    # ── 检测旧实例并杀掉 ──
    old_pid = None
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "18124" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts and parts[-1].isdigit():
                    old_pid = int(parts[-1])
                    break
    except Exception as e:
        print(f"  [清理] 检测端口失败: {e}")

    if old_pid:
        try:
            subprocess.run(
                ["taskkill", "/f", "/pid", str(old_pid)],
                capture_output=True, timeout=5
            )
            print(f"  [清理] 已终止旧进程 (PID={old_pid})")
            time.sleep(1.5)
        except Exception as e:
            print(f"  [清理] 终止进程失败: {e}")

    # ── 覆盖部署到 APPDATA（原地覆盖，保留目录创建时间/元数据，托盘设置不丢失）──
    os.makedirs(deploy_root, exist_ok=True)
    print(f"  [部署] 覆盖到 {deploy_dir} ...")
    try:
        shutil.copytree(dist_app, deploy_dir, dirs_exist_ok=True, ignore_dangling_symlinks=True)
    except PermissionError:
        shutil.copytree(dist_app, deploy_dir, dirs_exist_ok=True, copy_function=shutil.copy, ignore_dangling_symlinks=True)

    deploy_size = 0
    for dirpath, _, filenames in os.walk(deploy_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            deploy_size += os.path.getsize(fp)
    deploy_mb = deploy_size / (1024 * 1024)

    print("  [部署] 完成! 已部署到:")
    print(f"          {deploy_exe}")
    print(f"          大小: {deploy_mb:.1f} MB")
    print("          路径固定 → 托盘图标设置不再丢失")
    print()


def build():
    print(f"\n{'='*60}")
    print(f"  策划工具箱 — PyInstaller 打包")
    print(f"  版本: {APP_VERSION}")
    print(f"  工作区: {WORKSPACE}")
    print(f"{'='*60}\n")

    # ── Step 1: 检查 PyInstaller ──
    pyi = _get_pyinstaller()
    if not pyi:
        print("[错误] 未找到 PyInstaller。请先安装：pip install pyinstaller")
        sys.exit(1)
    print(f"[PyInstaller] {pyi}")

    # ── Step 2: 准备 worker 脚本 ──
    copied_workers = _ensure_worker_scripts()

    # ── Step 3: 生成时间戳 ──
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    ts_name = f"{APP_NAME}_{APP_VERSION}_{ts}"
    ts_app = os.path.join(DIST_DIR, ts_name)

    # PyInstaller 输出固定到 dist/策划工具箱/（--name APP_NAME），
    # 打包完成后用 copytree 创建时间戳归档（不 rename，避免权限问题）
    pyi_out = os.path.join(DIST_DIR, APP_NAME)
    dist_app = pyi_out

    build_dir = os.path.join(WORKSPACE, "build")

    # 清理 build 临时目录（不是输出目录，不影响旧包）
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    spec_file = os.path.join(WORKSPACE, f"{APP_NAME}.spec")
    if os.path.isfile(spec_file):
        os.remove(spec_file)

    # ── Step 4: 准备打包配置 ──
    cfg_safe = _strip_api_key()

    entry = os.path.join(WORKSPACE, "main.py")
    icon = os.path.join(CORE_DIR, "assets", "app_icon.ico")
    data_args = _get_data_args()
    hidden_imports = _get_hidden_imports()
    path_args = _get_path_args()

    # ── Step 5: 执行 PyInstaller ──
    cmd = [
        pyi,
        "--onedir",
        "--noconfirm",
        "--noconsole",
        "--clean",
        "--distpath", DIST_DIR,
        "--workpath", build_dir,
        "--name", APP_NAME,
        "--specpath", WORKSPACE,
    ]
    if os.path.isfile(icon):
        cmd += ["--icon", icon]
    cmd += data_args
    cmd += hidden_imports
    cmd += path_args
    cmd.append(entry)

    print(f"\n[执行] PyInstaller 打包中...")
    print(f"  Entry: {os.path.basename(entry)}")
    print(f"  Output: {dist_app}\\")
    sys.stdout.flush()

    result = subprocess.run(cmd, cwd=WORKSPACE, shell=True)
    if result.returncode != 0:
        _cleanup_copied_workers(copied_workers)
        print(f"\n[错误] PyInstaller 打包失败 (exit={result.returncode})")
        sys.exit(1)

    _cleanup_copied_workers(copied_workers)

    if not os.path.isdir(dist_app):
        print(f"\n[错误] 输出目录未生成: {dist_app}")
        sys.exit(1)

    # ── 创建时间戳归档（copytree，不改 exe 文件名）──
    if os.path.exists(ts_app):
        shutil.rmtree(ts_app)
    try:
        shutil.copytree(dist_app, ts_app, ignore_dangling_symlinks=True)
        print(f"  [归档] {APP_NAME}/ → {os.path.basename(ts_app)}/")
    except Exception as e:
        print(f"  [归档] 跳过 ({e})")

    print(f"\n[完成] PyInstaller 打包成功！")

    # ── Step 6: 复制配置文件（无 API Key + 保留窗口尺寸）──
    if cfg_safe is not None:
        cfg_name = "svn_gui_config.json"
        dst = os.path.join(dist_app, "_internal", CORE_DIR.split("\\")[-1], cfg_name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(os.path.join(CORE_DIR, cfg_name), "r", encoding="utf-8") as f:
            orig_cfg = json.load(f)
        for key in ("window_w", "window_h"):
            if key in orig_cfg:
                cfg_safe[key] = orig_cfg[key]
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(cfg_safe, f, ensure_ascii=False, indent=2)
        print(f"  [配置] (无 API Key) → _internal/toolbox_core/{cfg_name}")
        if "window_w" in cfg_safe:
            print(f"  [尺寸] {cfg_safe['window_w']}x{cfg_safe['window_h']}")

    # ── Step 7: 复制 update_version.py 到 dist ──
    ver_src = os.path.join(CORE_DIR, "update_version.py")
    ver_dst = os.path.join(dist_app, "_internal", CORE_DIR.split("\\")[-1], "update_version.py")
    if os.path.isfile(ver_src):
        shutil.copy2(ver_src, ver_dst)
        print(f"  [版本] update_version.py → _internal/toolbox_core/")

    # ── Step 8: 统计 ──
    total_size = 0
    for dirpath, _, filenames in os.walk(dist_app):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    file_count = sum(len(files) for _, _, files in os.walk(dist_app))
    size_mb = total_size / (1024 * 1024)

    print(f"\n{'='*60}")
    print(f"  打包完成！")
    print(f"  输出: {dist_app}\\")
    print(f"  文件: {file_count} 个")
    print(f"  大小: {size_mb:.1f} MB")
    print(f"{'='*60}")

    # ── Step 9: 部署到 APPDATA（固定路径，托盘设置不丢失）──
    _deploy_to_appdata(dist_app)

    return dist_app


def make_update_zip(dist_app):
    """将 dist 目录压缩为更新 zip 包，放入 update-server/"""
    os.makedirs(UPDATE_DIR, exist_ok=True)
    zip_name = f"{APP_NAME}_{APP_VERSION}.zip"
    zip_path = os.path.join(UPDATE_DIR, zip_name)

    print(f"\n[压缩] 生成更新包...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, filenames in os.walk(dist_app):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                rel = os.path.relpath(fp, os.path.dirname(dist_app))
                zf.write(fp, rel)
    zip_size = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  {zip_name} ({zip_size:.1f} MB)")

    # ── 计算 MD5 ──
    md5 = hashlib.md5()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    md5_hex = md5.hexdigest()

    # ── 生成 version.json（保留已有字段，只更新 md5）──
    ver_path = os.path.join(UPDATE_DIR, "version.json")
    if os.path.isfile(ver_path):
        with open(ver_path, "r", encoding="utf-8") as f:
            ver_info = json.load(f)
    else:
        ver_info = {
            "version": APP_VERSION,
            "url": zip_name,
            "md5": "",
            "notes": "",
            "force": False,
        }
    ver_info["md5"] = md5_hex
    with open(ver_path, "w", encoding="utf-8") as f:
        json.dump(ver_info, f, ensure_ascii=False, indent=2)
    print(f"  version.json → {UPDATE_DIR}\\")

    print(f"\n[更新服务器就绪]")
    print(f"  cd {UPDATE_DIR}")
    print(f"  python -m http.server 8080")
    print(f"  客户端地址: http://你的IP:8080/")

    return zip_path


if __name__ == "__main__":
    make_zip = "--zip" in sys.argv
    dist_app = build()
    if make_zip:
        make_update_zip(dist_app)
    else:
        print(f"\n提示: 加 --zip 参数可同时生成 update-server 下的更新包")
