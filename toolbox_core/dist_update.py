#!/usr/bin/env python3
"""
从现有打包目录 `dist/策划工具箱/` 生成更新 zip + 更新 version.json
用法:
  python dist_update.py              # 从 dist/策划工具箱/ 生成 zip
  python dist_update.py --dir <路径> # 从指定目录生成

原理：PyInstaller 打包一次（~5分钟）后，后续发版只需压缩+算 MD5（~30秒）
"""
import os
import sys
import json
import hashlib
import zipfile

WORKSPACE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(WORKSPACE, "dist")
UPDATE_DIR = os.path.join(WORKSPACE, "update-server")
APP_NAME = "策划工具箱"


def _get_version(dist_app):
    """读取版本号：优先用工作区的 update_version.py（源码的版本号总是最新的）"""
    ws_ver = os.path.join(os.path.dirname(__file__), "update_version.py")
    if os.path.isfile(ws_ver):
        for line in open(ws_ver, encoding="utf-8"):
            if "APP_VERSION" in line and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    # fallback: 从打包目录读
    for p in (os.path.join(dist_app, "_internal", "toolbox_core", "update_version.py"),
              os.path.join(dist_app, f"{APP_NAME}_internal", "toolbox_core", "update_version.py")):
        if os.path.isfile(p):
            for line in open(p, encoding="utf-8"):
                if "APP_VERSION" in line and "=" in line:
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "v1.0"


def make_update_zip(dist_app, version=None):
    """从 dist_app 目录生成 zip，返回 (zip_path, md5_hex)"""
    if version is None:
        version = _get_version(dist_app)

    os.makedirs(UPDATE_DIR, exist_ok=True)
    zip_name = f"{APP_NAME}_{version}.zip"
    zip_path = os.path.join(UPDATE_DIR, zip_name)

    print(f"[压缩] {dist_app} → {zip_name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, filenames in os.walk(dist_app):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                rel = os.path.relpath(fp, os.path.dirname(dist_app))
                zf.write(fp, rel)

    md5 = hashlib.md5()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    md5_hex = md5.hexdigest()
    zip_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  {zip_name} ({zip_mb:.1f} MB)  MD5: {md5_hex}")
    return zip_path, md5_hex


def update_version_json(version, md5_hex, notes="", force=True):
    """更新/补填 version.json"""
    ver_path = os.path.join(UPDATE_DIR, "version.json")
    if os.path.isfile(ver_path):
        with open(ver_path, "r", encoding="utf-8") as f:
            ver_info = json.load(f)
    else:
        ver_info = {"version": version, "url": f"{APP_NAME}_{version}.zip", "md5": "", "notes": "", "force": False}

    ver_info["version"] = version
    ver_info["url"] = f"{APP_NAME}_{version}.zip"
    ver_info["md5"] = md5_hex
    if notes:
        ver_info["notes"] = notes
    if force is not None:
        ver_info["force"] = force

    with open(ver_path, "w", encoding="utf-8") as f:
        json.dump(ver_info, f, ensure_ascii=False, indent=2)
    print(f"  version.json 已更新: {version}, force={ver_info['force']}")


def main():
    pyi_out = os.path.join(DIST_DIR, APP_NAME)  # dist/策划工具箱/

    # 支持 --dir 参数指定源目录
    src = pyi_out
    for i, a in enumerate(sys.argv[1:]):
        if a == "--dir" and i + 1 < len(sys.argv):
            src = os.path.abspath(sys.argv[i + 2])
            break

    if not os.path.isdir(src):
        print(f"[错误] 源目录不存在: {src}")
        print(f"用法: python dist_update.py")
        print(f"      python dist_update.py --dir dist/策划工具箱_v1.0.2_时间戳/")
        sys.exit(1)

    version = _get_version(src)
    if not version:
        print("[错误] 无法读取版本号，确保目录包含 _internal/toolbox_core/update_version.py")
        sys.exit(1)

    print(f"版本: {version}")
    print(f"源目录: {src}")

    zip_path, md5_hex = make_update_zip(src, version)
    update_version_json(version, md5_hex)

    print(f"\n[完成] 更新包就绪")
    print(f"  zip: {zip_path}")
    print(f"  启动: cd {UPDATE_DIR} && python -m http.server 8080")


if __name__ == "__main__":
    main()
