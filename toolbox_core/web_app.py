#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 - Web 版本 (Flask 后端)"""
import sys
import os
import json
import signal
import subprocess
import threading
import queue
import time
import shutil
import stat
import tempfile
import concurrent.futures
from datetime import datetime
import locale
import re

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pm = os.path.join(_script_dir, "py_modules")
if not os.path.isdir(_pm):
    _pm = os.path.join(os.path.dirname(_script_dir), "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)
    # 手动添加 pywin32 需要的子目录
    for subdir in ["win32", "win32\\lib", "pythonwin"]:
        full_path = os.path.join(_pm, subdir)
        if os.path.isdir(full_path) and full_path not in sys.path:
            sys.path.insert(0, full_path)
sys.path.insert(0, _script_dir)

# 添加 py_modules 到 DLL 搜索路径和 PATH
if os.path.isdir(_pm):
    pywin32_dll = os.path.join(_pm, "pywin32_system32")
    if os.path.isdir(pywin32_dll):
        os.add_dll_directory(pywin32_dll)
    os.add_dll_directory(_pm)
    # 也加到 PATH 环境变量
    os.environ["PATH"] = _pm + os.pathsep + os.environ.get("PATH", "")
    # 设置 Tcl/Tk 环境变量
    tcl_dir = os.path.join(_pm, "_tcl_data")
    tk_dir = os.path.join(_pm, "_tk_data")
    if os.path.isdir(tcl_dir):
        os.environ["TCL_LIBRARY"] = tcl_dir
    if os.path.isdir(tk_dir):
        os.environ["TK_LIBRARY"] = tk_dir

from flask import Flask, render_template, request, jsonify, Response, send_from_directory, stream_with_context  # noqa: E402
from webview.dom import _dnd_state

from toolbox_config import (  # noqa: E402
    SCRIPT_DIR, MAIN_SCRIPT, DEFAULT_OUTPUT_DIR,
    load_config, save_config,
)
from toolbox_platform import _get_subprocess_kwargs, _get_bat_subprocess_kwargs, _get_svn_path, _check_office_lock, _diagnose_svn_missing, _auto_install_svn_cli  # noqa: E402
from xlsm_zipper import apply_via_excel  # noqa: E402
from toolbox_merge import svn_log, svn_merge, open_commit_dialog, resolve_target_path, resolve_svn_url_to_local, migrate_old_svn_mappings  # noqa: E402

if len(sys.argv) >= 2 and sys.argv[1] == "--worker":
    if len(sys.argv) < 3:
        print("Usage: --worker <worker_script> [args...]", file=sys.stderr)
        sys.exit(1)
    worker_script = sys.argv[2]
    worker_args = sys.argv[3:]
    env = os.environ.copy()
    pm = os.path.join(_script_dir, "py_modules")
    if not os.path.isdir(pm):
        pm = os.path.join(os.path.dirname(_script_dir), "py_modules")
    if os.path.isdir(pm):
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pm if not existing else pm + os.pathsep + existing
    q = queue.Queue()
    proc = subprocess.Popen(
        [sys.executable, worker_script] + worker_args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace",
        bufsize=1, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    for line in iter(proc.stdout.readline, ""):
        q.put(line)
    proc.wait()
    q.put(None)
    sys.exit(proc.returncode)

_quit_app_callback = lambda: None

app = Flask(__name__)
# 生产环境关闭模板自动重载（减少文件系统调用）
if os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true"):
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

# 启动时自动从旧配置迁移 SVN URL↔路径映射
try:
    cfg = load_config()
    if not cfg.get("svn_url_mappings"):
        migrate_old_svn_mappings(cfg)
except Exception:
    pass


@app.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ── SSE 日志流 ───────────────────────────────────────────
_log_queues = {}  # task_id -> queue.Queue


def _get_next_task_id():
    return str(int(time.time() * 1000))


_active_subprocesses = []
_active_tasks = {}
_cancelled_tasks = set()
_procs_lock = threading.Lock()
_cancel_lock = threading.Lock()


def _cancel_all_tasks():
    """Kill all running subprocesses (SVN, Upload, Workflow) before update"""
    count = 0
    with _procs_lock:
        for proc in list(_active_subprocesses):
            try:
                proc.kill()
                proc.wait(timeout=5)
                count += 1
            except Exception:
                pass
        _active_tasks.clear()
        _active_subprocesses.clear()
    return count


def _register_proc(proc, task_id=None):
    with _procs_lock:
        _active_subprocesses.append(proc)
        if task_id:
            _active_tasks.setdefault(task_id, []).append(proc)


def _unregister_proc(proc, task_id=None):
    with _procs_lock:
        try:
            _active_subprocesses.remove(proc)
        except ValueError:
            pass
        if task_id:
            procs = _active_tasks.get(task_id, [])
            try:
                procs.remove(proc)
            except ValueError:
                pass
            if not procs and task_id in _active_tasks:
                del _active_tasks[task_id]


def _handle_shutdown(signum, frame):
    with _procs_lock:
        for proc in list(_active_subprocesses):
            try:
                proc.kill()
                proc.communicate(timeout=5)
            except Exception:
                pass
    _log_queues.clear()
    sys.exit(0)


if threading.current_thread() is threading.main_thread():
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown)
    except AttributeError:
        pass
    signal.signal(signal.SIGINT, _handle_shutdown)

# ═══════════════════════════════════════════════════════════
# 页面
# ═══════════════════════════════════════════════════════════


@app.route("/")
def index():
    return render_template("index.html")

# ═══════════════════════════════════════════════════════════
# 配置 API
# ═══════════════════════════════════════════════════════════


@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = load_config()
    safe = {
        "svn_urls": cfg.get("svn_urls", []),
        "svn_url_current": cfg.get("svn_url_current", ""),
        "merge_source_current": cfg.get("merge_source_current", ""),
        "src_dir_history": cfg.get("src_dir_history", []),
        "tgt_dir_history": cfg.get("tgt_dir_history", []),
        "tr_src_history": cfg.get("tr_src_history", []),
        "tr_ref_history": cfg.get("tr_ref_history", []),
        "tr_api_url": cfg.get("tr_api_url", "https://api.openai.com/v1/chat/completions"),
        "tr_model": cfg.get("tr_model", "gpt-4o-mini"),
        "tr_src_lang": cfg.get("tr_src_lang", "zh"),
        "tr_out_dir": cfg.get("tr_out_dir", DEFAULT_OUTPUT_DIR),
        "tr_prompt": cfg.get("tr_prompt", "请将以下文本翻译为{tgt_lang}，保持格式不变"),
        "tr_batch_size": cfg.get("tr_batch_size", 20),
        "tr_lang_id_map": cfg.get("tr_lang_id_map", {}),
        "tr_saved_tgt_langs": cfg.get("tr_saved_tgt_langs", []),
        "output_dir": cfg.get("output_dir", DEFAULT_OUTPUT_DIR),
        "output_dir_history": cfg.get("output_dir_history", []),
        "merge_target_history": cfg.get("merge_target_history", []),
        "merge_revert_exclude_paths": cfg.get("merge_revert_exclude_paths", []),
        "svn_keyword_history": cfg.get("svn_keyword_history", []),
        "svn_author_history": cfg.get("svn_author_history", []),
        "exclude_dirs": cfg.get("exclude_dirs", ""),
        "svn_user": cfg.get("svn_user", ""),
        "cmp_file_presets": cfg.get("cmp_file_presets", []),
        "cmp_file_settings": cfg.get("cmp_file_settings", {}),
        "cmp_title_rows": cfg.get("cmp_title_rows", "1"),
        "cmp_id_col": cfg.get("cmp_id_col", "::ID::"),
        "cmp_global_id_col": cfg.get("cmp_global_id_col", ""),
        "cmp_output_cols": cfg.get("cmp_output_cols", ""),
        "workflows": cfg.get("workflows", []),
        "tr_api_key": cfg.get("tr_api_key", ""),
        "_wf_history_paths": cfg.get("_wf_history_paths", []),
        "_wf_history_texts": cfg.get("_wf_history_texts", []),
        "_wf_history_msgs": cfg.get("_wf_history_msgs", []),
        "merge_file_filter_mode": cfg.get("merge_file_filter_mode", "include"),
        "merge_file_filter_include_text": cfg.get("merge_file_filter_include_text", ""),
        "merge_file_filter_exclude_text": cfg.get("merge_file_filter_exclude_text", ""),
    }
    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
def api_save_config():
    cfg = load_config()
    data = request.get_json(force=True)
    for k, v in data.items():
        if k == "api_key" and v:
            cfg["tr_api_key"] = v
        elif k == "svn_pass" and v:
            from toolbox_config import encrypt_key
            cfg["svn_pass"] = encrypt_key(v)
        elif k in ("api_key", "svn_pass"):
            pass
        else:
            cfg[k] = v
    save_config(cfg)
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════
# SVN 执行 API
# ═══════════════════════════════════════════════════════════


def _run_svn_task(q, svn_url, mode, start_date, end_date, keyword, author, output, cfg, task_id):
    # 子进程需要能找到 py_modules 里的依赖（如 lxml）
    _pm_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "py_modules")
    _svn_env = {**os.environ, "PYTHONPATH": _pm_path} if os.path.isdir(_pm_path) else None

    q.put(f"{'='*50}\n")
    q.put("开始执行\n")
    q.put(f"模式: {mode}\n")
    q.put(f"SVN URL: {svn_url}\n")
    q.put(f"日期范围: {start_date} ~ {end_date}\n")
    q.put(f"输出: {output}\n")

    cmd = [sys.executable, MAIN_SCRIPT, "--url", svn_url,
           "--start", start_date, "--end", end_date, "--output", output]
    if mode == "export":
        cmd += ["--export", "--export-dir", output]
        exclude = cfg.get("exclude_dirs", "").strip()
        if exclude:
            cmd += ["--exclude-dirs", exclude]
    elif mode == "summary":
        cmd += ["--summary", "--export-dir", output]
        exclude = cfg.get("exclude_dirs", "").strip()
        if exclude:
            cmd += ["--exclude-dirs", exclude]
    if keyword:
        for kw in keyword.split(","):
            kw = kw.strip()
            if kw:
                cmd += ["--keyword", kw]
    if author:
        cmd += ["--author", author]

    svn_user = cfg.get("svn_user", "").strip()
    svn_pass = cfg.get("svn_pass", "").strip()
    if svn_user:
        cmd += ["--svn-user", svn_user]
    if svn_pass:
        from toolbox_config import decrypt_key
        cmd += ["--svn-pass", decrypt_key(svn_pass)]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding="utf-8", errors="replace",
                                bufsize=1, env=_svn_env,
                                **_get_subprocess_kwargs())
        _register_proc(proc, task_id)
        try:
            for line in iter(proc.stdout.readline, ""):
                q.put(line)
            proc.wait()
            q.put(f"\n── 执行完成 (退出码: {proc.returncode}) ──\n")
        finally:
            _unregister_proc(proc, task_id)
    except Exception as e:
        q.put(f"\n❌ 执行失败: {e}\n")
    q.put(f"[输出路径] {output}\n")
    with _cancel_lock:
        cancelled = task_id in _cancelled_tasks
    if not cancelled:
        mode_names = {"compare": "SVN 对比", "export": "SVN 导出", "summary": "SVN 摘要"}
        _notify_task_done(mode_names.get(mode, f"SVN {mode}"))
    with _cancel_lock:
        _cancelled_tasks.discard(task_id)
    q.put(None)


@app.route("/api/svn/run", methods=["POST"])
def api_svn_run():
    data = request.get_json(force=True)
    svn_url = data.get("svn_url", "").strip()
    mode = data.get("mode", "compare")
    start_date = data.get("start_date", "")
    end_date = data.get("end_date", "")
    keyword = data.get("keyword", "").strip()
    author = data.get("author", "").strip()
    output = data.get("output", DEFAULT_OUTPUT_DIR).strip()

    if not svn_url:
        return jsonify({"error": "请输入 SVN URL"}), 400

    cfg = load_config()
    urls = cfg.get("svn_urls", [])
    if svn_url in urls:
        urls.remove(svn_url)
    urls.insert(0, svn_url)
    cfg["svn_urls"] = urls[:20]
    save_config(cfg)

    is_export_like = mode in ("export", "summary")
    if not output or not os.path.isdir(output):
        output = DEFAULT_OUTPUT_DIR
    os.makedirs(output, exist_ok=True)

    if is_export_like:
        for fname in os.listdir(output):
            fpath = os.path.join(output, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
            except Exception:
                pass

    task_id = _get_next_task_id()
    q = queue.Queue()
    _log_queues[task_id] = q
    threading.Thread(target=_run_svn_task, args=(q, svn_url, mode, start_date, end_date, keyword, author, output, cfg, task_id), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/task/cancel", methods=["POST"])
def api_task_cancel():
    data = request.get_json(force=True)
    task_id = data.get("task_id", "").strip()
    if not task_id:
        return jsonify({"error": "缺少 task_id"}), 400

    with _procs_lock:
        procs = _active_tasks.pop(task_id, [])
    for proc in procs:
        try:
            proc.kill()
            proc.communicate(timeout=5)
        except Exception:
            pass
        with _procs_lock:
            try:
                _active_subprocesses.remove(proc)
            except ValueError:
                pass

    q = _log_queues.pop(task_id, None)
    if q:
        try:
            q.put(json.dumps({"type": "cancelled", "message": "任务已取消"}, ensure_ascii=False))
            q.put(None)
        except Exception:
            pass

    with _cancel_lock:
        _cancelled_tasks.add(task_id)

    return jsonify({"status": "cancelled", "task_id": task_id})

# ═══════════════════════════════════════════════════════════
# 文件浏览 API（上传页签用）
# ═══════════════════════════════════════════════════════════


@app.route("/api/files/list", methods=["POST"])
def api_file_list():
    data = request.get_json(force=True)
    path = data.get("path", "").strip()
    if not path or not os.path.isdir(path):
        return jsonify({"error": "无效目录"}), 400

    entries = []
    try:
        items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
        for name in items:
            fp = os.path.join(path, name)
            try:
                st = os.stat(fp)
                is_dir = os.path.isdir(fp)
                if is_dir:
                    total = 0
                    for r, _, fs in os.walk(fp):
                        for f in fs:
                            try:
                                total += os.path.getsize(os.path.join(r, f))
                            except Exception:
                                pass
                    size = total
                else:
                    size = st.st_size
                if size >= 1024*1024:
                    s = f"{size/1024/1024:.1f}MB"
                elif size >= 1024:
                    s = f"{size/1024:.1f}KB"
                else:
                    s = f"{size}B"
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                is_dir = os.path.isdir(fp)
                s = "-"
                mtime = "-"
            entries.append({
                "name": name, "path": fp, "is_dir": is_dir,
                "size": s, "date": mtime,
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"entries": entries, "path": path})


def _get_drives():
    drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            drives.append({"name": f"{letter}:", "path": root})
    return drives


@app.route("/api/path/verify", methods=["POST"])
def api_path_verify():
    data = request.get_json(force=True)
    path = data.get("path", "").strip()
    if not path:
        return jsonify({"ok": False})
    return jsonify({"ok": os.path.isdir(path)})


@app.route("/api/dir/browse", methods=["POST"])
def api_dir_browse():
    data = request.get_json(force=True)
    path = os.path.normpath(data.get("path", os.path.expanduser("~")))
    if not os.path.isdir(path):
        path = os.path.normpath(os.path.expanduser("~"))

    dirs = []
    try:
        items = sorted(os.listdir(path), key=lambda x: x.lower())
        for name in items:
            fp = os.path.join(path, name)
            if os.path.isdir(fp) and not name.startswith("."):
                dirs.append({"name": name, "path": fp})
    except Exception:
        pass

    parent = os.path.dirname(path) if path else ""
    return jsonify({"dirs": dirs, "current": os.path.normpath(path), "parent": parent, "drives": _get_drives()})

# ═══════════════════════════════════════════════════════════
# 上传执行 API
# ═══════════════════════════════════════════════════════════


def _decode_svn_output(data):
    try:
        return data.decode("gbk")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _svn_update_first(q, target_dir):
    svn_exe = _get_svn_path()
    q.put("正在更新 SVN 工作副本...\n")
    try:
        r = subprocess.run(
            [svn_exe, "update", target_dir],
            capture_output=True, text=False,
            timeout=120, **_get_subprocess_kwargs()
        )
        text = _decode_svn_output(r.stdout)
        if r.returncode == 0:
            for line in text.strip().splitlines():
                line = line.strip()
                if line:
                    q.put(f"  {line}\n")
            q.put("SVN 更新完成\n")
        else:
            err_text = _decode_svn_output(r.stderr)
            q.put("SVN 更新失败: " + err_text.strip() + "\n")
    except subprocess.TimeoutExpired:
        q.put("SVN 更新超时（超过2分钟）\n")
    except Exception as e:
        q.put("SVN 更新异常: " + str(e) + "\n")
        if "系统找不到指定的文件" in str(e):
            q.put("  💡 " + _diagnose_svn_missing().replace("\n", "\n     ") + "\n")
            q.put("  → 正在自动安装 SVN 命令行工具...\n")
            _put = lambda msg: q.put("     " + msg)
            ok, msg = _auto_install_svn_cli(put=_put)
            q.put(f"  → {msg}\n")


def _run_svn_after_upload(q, target_dir, copied_files):  # noqa: C901
    q.put(f"\n{'─'*40}\n")
    q.put("开始SVN上传\n")

    svn_exe = _get_svn_path()
    result = subprocess.run(
        [svn_exe, "info", target_dir],
        capture_output=True, timeout=15, **_get_subprocess_kwargs()
    )
    if result.returncode != 0:
        q.put("⚠️ 目标目录没有找到SVN链接，跳过\n")
        return

    wc_r = subprocess.run(
        [svn_exe, "info", "--show-item", "wc-root", target_dir],
        capture_output=True, timeout=15, **_get_subprocess_kwargs()
    )
    wc_root = _decode_svn_output(wc_r.stdout).strip() if wc_r.returncode == 0 else ""
    q.put(f"   ✅ SVN 链接验证通过，即将提交 {len(copied_files)} 个文件\n")

    try:
        r_status = subprocess.run(
            [svn_exe, "status", "--no-ignore", wc_root],
            capture_output=True, timeout=30, **_get_subprocess_kwargs()
        )
        if r_status.returncode == 0:
            status_stdout = _decode_svn_output(r_status.stdout)
            copied_abs = {os.path.abspath(f) for f in copied_files}
            revert_list = []
            for line in status_stdout.splitlines():
                if len(line) > 7 and line[0] == "A" and line[1] == " ":
                    status_path = line[7:].strip()
                    if not os.path.isabs(status_path):
                        status_path = os.path.join(wc_root, status_path)
                    status_path = os.path.abspath(status_path)
                    if status_path not in copied_abs:
                        revert_list.append(status_path)
            if revert_list:
                for rf in revert_list:
                    subprocess.run(
                        [svn_exe, "revert", rf],
                        capture_output=True, timeout=10, **_get_subprocess_kwargs()
                    )
                q.put(f"   🧹 已清理 {len(revert_list)} 个未提交的 add 记录\n")
    except Exception:
        pass

    # 用 --targets 批量 svn add，再用 svn status wc_root + 集合过滤检测变更
    targets = os.path.join(tempfile.mkdtemp(), "svn_targets.txt")
    changed = os.path.join(tempfile.mkdtemp(), "svn_changed.txt")
    changed_files = []
    try:
        with open(targets, "w", encoding="utf-8") as f:
            for fp in copied_files:
                f.write(os.path.abspath(fp) + "\n")
        subprocess.run(
            [svn_exe, "add", "--parents", "--force", "--quiet", "--targets", targets],
            capture_output=True, timeout=60, **_get_subprocess_kwargs()
        )
        r = subprocess.run(
            [svn_exe, "status", wc_root],
            capture_output=True, timeout=60, **_get_subprocess_kwargs()
        )
        status_stdout = _decode_svn_output(r.stdout)
        copied_abs = {os.path.abspath(f) for f in copied_files}
        changed_flags = {'M', 'A', 'R', '!', '?'}
        for line in status_stdout.splitlines():
            if len(line) < 2:
                continue
            flag = line[0]
            if flag not in changed_flags:
                continue
            p = line[7:].strip() if len(line) > 7 else ""
            if not p:
                continue
            if not os.path.isabs(p):
                p = os.path.join(wc_root, p)
            p = os.path.abspath(p)
            if p in copied_abs:
                changed_files.append(p)
        q.put(f"   ✅ 已添加 {len(copied_files)} 个文件，其中 {len(changed_files)} 个有实际变化\n")
        subprocess.run(
            [svn_exe, "changelist", "--remove", "--changelist", "本次修改", wc_root, "--depth", "infinity"],
            capture_output=True, timeout=60, **_get_subprocess_kwargs()
        )
        if changed_files:
            with open(changed, "w", encoding="utf-8") as f:
                for fp in changed_files:
                    f.write(fp + "\n")
            subprocess.run(
                [svn_exe, "changelist", "本次修改", "--targets", changed],
                capture_output=True, timeout=60, **_get_subprocess_kwargs()
            )
            q.put(f"   🏷️ 已标记 {len(changed_files)} 个文件 changelist 分组\n")
        else:
            q.put("   🏷️ 无变化的文件，跳过 changelist 标记\n")
    except Exception:
        pass
    finally:
        for f in [targets, changed]:
            try:
                os.unlink(f)
                os.rmdir(os.path.dirname(f))
            except Exception:
                pass

    if not changed_files:
        q.put("⚠️ 没有实际变化的文件，跳过 TortoiseSVN 提交对话框\n")
    else:
        tortoise = _get_tortoise_proc_path()
        if tortoise:
            q.put(f"🖥️ 正在打开 TortoiseSVN 提交对话框 ({len(changed_files)} 个文件)...\n")
            subprocess.Popen([tortoise, "/command:commit", f"/path:{wc_root}"])
            q.put("✅ TortoiseSVN 提交对话框已打开\n")
        else:
            q.put("⚠️ 未找到 TortoiseSVN\n")


def _copy2_force(src, dst):
    if os.path.exists(dst):
        try:
            os.chmod(dst, stat.S_IWRITE | stat.S_IREAD)
        except Exception:
            pass
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        try:
            os.remove(dst)
        except Exception:
            pass
        shutil.copy2(src, dst)


def _run_upload_copy(src, tgt, files, q, task_id):
    q.put(f"{'='*50}\n")
    q.put("开始上传\n")
    q.put(f"源: {src}\n")
    q.put(f"目标: {tgt}\n\n")

    svn_exe = _get_svn_path()
    result = subprocess.run(
        [svn_exe, "info", tgt],
        capture_output=True, text=False,
        timeout=15, **_get_subprocess_kwargs()
    )
    if result.returncode == 0:
        wc_r = subprocess.run(
            [svn_exe, "info", "--show-item", "wc-root", tgt],
            capture_output=True, text=False,
            timeout=15, **_get_subprocess_kwargs()
        )
        wc_root = _decode_svn_output(wc_r.stdout).strip()
        if wc_root:
            _svn_update_first(q, wc_root)

    q.put("开始复制文件...\n")
    success = fail = 0
    copied_files = []
    for fi in files:
        name = fi["name"]
        sp = fi["path"]
        is_dir = fi.get("is_dir", False)
        try:
            if is_dir:
                target_dir = os.path.join(tgt, name)
                if os.path.isdir(target_dir):
                    q.put(f"📂 {name}/ 已存在，合并文件...\n")
                shutil.copytree(sp, target_dir, dirs_exist_ok=True, copy_function=_copy2_force)
                for rp, _, fns in os.walk(sp):
                    rel = os.path.relpath(rp, sp)
                    for fn in fns:
                        copied_files.append(os.path.join(target_dir, rel, fn))
                q.put(f"✓ {name}/ 文件夹已复制\n")
            else:
                dst = os.path.join(tgt, name)
                _copy2_force(sp, dst)
                copied_files.append(dst)
                q.put(f"✓ {name}\n")
            success += 1
        except Exception as e:
            fail += 1
            q.put(f"✗ {name}: {e}\n")
    q.put(f"\n── 文件复制完成: {success} 成功, {fail} 失败 ──\n")

    if success > 0:
        _run_svn_after_upload(q, tgt, copied_files)

    _notify_task_done("上传SVN")
    q.put(None)
    _log_queues.pop(task_id, None)


@app.route("/api/upload/run", methods=["POST"])
def api_upload_run():
    data = request.get_json(force=True)
    src = data.get("src_dir", "").strip()
    tgt = data.get("tgt_dir", "").strip()
    files = data.get("files", [])

    if not src or not os.path.isdir(src):
        return jsonify({"error": "无效源目录"}), 400
    if not tgt or not os.path.isdir(tgt):
        return jsonify({"error": "无效目标目录"}), 400
    if not files:
        return jsonify({"error": "请选择文件"}), 400

    cfg = load_config()
    for k, v in [("src_dir_history", src), ("tgt_dir_history", tgt)]:
        hist = cfg.get(k, [])
        if v in hist:
            hist.remove(v)
        hist.insert(0, v)
        cfg[k] = hist[:20]
    save_config(cfg)

    task_id = _get_next_task_id()
    q = queue.Queue()
    _log_queues[task_id] = q
    threading.Thread(target=_run_upload_copy, args=(src, tgt, files, q, task_id), daemon=True).start()
    return jsonify({"task_id": task_id})

@app.route("/api/prefab/scan", methods=["POST"])
def api_prefab_scan():
    data = request.get_json(force=True)
    paths = data.get("paths", [])
    if not paths:
        return jsonify({"error": "请提供路径"}), 400
    files = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        if os.path.isfile(p) and p.lower().endswith(".prefab"):
            files.append(p)
        elif os.path.isdir(p):
            for root, dirs, fnames in os.walk(p):
                for fn in fnames:
                    if fn.lower().endswith(".prefab"):
                        files.append(os.path.join(root, fn))
    files.sort(key=lambda x: x.lower())
    return jsonify({"files": files, "count": len(files)})


@app.route("/api/prefab/consume-dropped", methods=["POST"])
def api_prefab_consume_dropped():
    paths = [p[1] for p in _dnd_state.get('paths', [])]
    _dnd_state['paths'].clear()
    return jsonify({"paths": paths, "count": len(paths)})

@app.route("/api/prefab/clear-text", methods=["POST"])
def api_prefab_clear_text():
    data = request.get_json(force=True)
    files = data.get("files", [])
    if not files:
        return jsonify({"error": "请提供 .prefab 文件列表"}), 400

    task_id = _get_next_task_id()
    q = queue.Queue()
    _log_queues[task_id] = q
    threading.Thread(target=_exec_prefab_clear_text, args=(files, q, task_id), daemon=True).start()
    return jsonify({"task_id": task_id})



def _exec_prefab_clear_text(files, q, task_id):
    total_cleared = 0
    total_files = 0
    for fp in files:
        if not fp.lower().endswith(".prefab"):
            q.put("[\u8df3\u8fc7] " + os.path.basename(fp) + " \u2014 \u4e0d\u662f .prefab \u6587\u4ef6\n")
            continue
        try:
            with open(fp, "rb") as f:
                raw_bytes = f.read()
            # Detect line endings
            lf_only = raw_bytes.count(b"\n") > 0 and b"\r\n" not in raw_bytes
            crlf = b"\r\n" in raw_bytes
            if lf_only:
                file_lines = raw_bytes.decode("utf-8").split("\n")
                nl = "\n"
            elif crlf:
                file_lines = raw_bytes.decode("utf-8").split("\r\n")
                nl = "\r\n"
            else:
                file_lines = [raw_bytes.decode("utf-8")]
                nl = "\n"
            new_lines = []
            cleared = 0
            for i, line in enumerate(file_lines):
                m = re.match(r"^( +)(m_Text:)(.*)$", line)
                if m and m.group(3).strip():
                    new_lines.append(m.group(1) + m.group(2))
                    val = m.group(3).strip()
                    msg = "[\u6e05\u7406] " + os.path.basename(fp) + " L" + str(i+1) + ": " + val[:50]
                    if len(val) > 50:
                        msg += "..."
                    msg += " \u2192 \u5df2\u6e05\u9664\n"
                    q.put(msg)
                    cleared += 1
                else:
                    new_lines.append(line)
            if cleared:
                with open(fp, "wb") as f:
                    f.write(nl.join(new_lines).encode("utf-8"))
                total_cleared += cleared
            total_files += 1
            q.put("[\u5b8c\u6210] " + os.path.basename(fp) + " \u2014 \u6e05\u7406 " + str(cleared) + " \u5904 m_Text\n")
        except Exception as e:
            q.put("[\u9519\u8bef] " + os.path.basename(fp) + ": " + str(e) + "\n")
    q.put("\n[DONE] \u5171\u5904\u7406 " + str(total_files) + " \u4e2a\u6587\u4ef6\uff0c\u6e05\u7406 " + str(total_cleared) + " \u5904\u6587\u672c\n")
    _notify_task_done("\u4e00\u952e\u6e05\u7406\u6587\u5b57")
    q.put(None)

@app.route("/api/workflow/list", methods=["GET"])
def api_workflow_list():
    cfg = load_config()
    return jsonify({"workflows": cfg.get("workflows", [])})


@app.route("/api/workflow/save", methods=["POST"])
def api_workflow_save():
    data = request.get_json(force=True)
    cfg = load_config()
    cfg["workflows"] = data.get("workflows", [])
    save_config(cfg)
    return jsonify({"ok": True})


# ── 桌面任务完成通知 ──────────────────────────────


def _focus_app_window():
    fn = getattr(sys.modules.get(__name__), '_on_notification_click', None)
    if fn:
        try:
            fn()
        except Exception:
            pass


def _is_window_visible():
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, "策划工具箱")
        if not hwnd:
            return True
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return False
        return ctypes.windll.user32.IsIconic(hwnd) == 0
    except Exception:
        return True


def _notify_task_done(name):
    if _is_window_visible():
        return
    try:
        ico_path = os.path.join(_script_dir, "assets", "app_icon.ico")
        if os.path.isfile(ico_path):
            toast_icon = os.path.join(
                os.environ.get("APPDATA", os.path.expanduser("~")),
                "planning-toolbox", "toast_icon.png"
            )
            if not os.path.isfile(toast_icon):
                try:
                    from PIL import Image
                    src = Image.open(ico_path)
                    if hasattr(src, 'seek'):
                        best = src
                        for i in range(src.n_frames if hasattr(src, 'n_frames') else 1):
                            src.seek(i)
                            w, h = src.size
                            if w >= 48 and h >= 48:
                                best = src.copy()
                                break
                        src = best
                    raw = src.convert("RGBA")
                    raw.thumbnail((34, 34), Image.LANCZOS)
                    canvas = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
                    left = (48 - raw.width) // 2
                    top = (48 - raw.height) // 2
                    canvas.paste(raw, (left, top), raw)
                    os.makedirs(os.path.dirname(toast_icon), exist_ok=True)
                    canvas.save(toast_icon, "PNG")
                except Exception:
                    toast_icon = None
        else:
            toast_icon = None

        from win11toast import toast
        toast(
            body=f"「{name}」任务已完成，点击查看结果",
            on_click=lambda args: _focus_app_window(),
            app_id="策划工具箱",
            icon=toast_icon,
        )
    except ImportError:
        pass
    except Exception:
        pass


def _run_wf_task(q, wf, steps, task_id):
    prefix = {"error": "❌ ", "ok": "✓ ", "warn": "⚠ ", "head": ""}

    def _put(msg, tag=""):
        if msg is None:
            q.put(None)
            return
        ts = datetime.now().strftime("%H:%M:%S")
        q.put(f"[{ts}] {msg}")

    def _line(msg, tag=""):
        if tag:
            _put(f"[{tag}] {prefix.get(tag, '')}{msg}\n")
        else:
            _put(f"{prefix.get(tag, '')}{msg}\n")

    _put(f"{'='*50}\n")
    _put(f"执行工作流: {wf.get('name', '未命名')}\n")
    _put(f"共 {len(steps)} 个步骤\n\n")

    blocked = False
    for i, step in enumerate(steps):
        with _cancel_lock:
            if task_id in _cancelled_tasks:
                _put("工作流已被取消\n")
                break
        _put(f"-- [{i+1}/{len(steps)}] {step.get('name', '')} --\n")
        if blocked:
            _put("已阻断，跳过\n")
            continue
        stype = step.get("type", "")
        ok = True
        try:
            if stype == "export_text":
                ok = _exec_export_text(step, _put, task_id)
            elif stype == "upload_svn":
                ok = _exec_upload_svn(step, _put, task_id)
            elif stype == "merge_table":
                ok = _exec_merge_table(step, _put, task_id)
            elif stype == "merge_translation":
                ok = _exec_merge_translation(step, _put, task_id)
            elif stype == "export_error_code":
                ok = _exec_export_error_code(step, _put, task_id)
            elif stype == "lock_svn":
                ok = _exec_lock_svn(step, _put, task_id)
            elif stype == "unlock_svn":
                ok = _exec_unlock_svn(step, _put, task_id)
            elif stype == "open_tables":
                ok = _exec_open_tables(step, _put, task_id)
            elif stype == "revert_svn":
                ok = _exec_revert_svn(step, _put, task_id)
            elif stype == "copy_files":
                ok = _exec_copy_files(step, _put, task_id)
            elif stype == "merge_error_code":
                ok = _exec_merge_error_code(step, _put, task_id)
            else:
                _line(f"未知步骤类型: {stype}", "error")
                ok = False
        except Exception as e:
            _line(str(e), "error")
            ok = False
        if not ok:
            _line("步骤执行失败，阻断后续步骤", "error")
            blocked = True
    _put(f"\n{'='*50}\n")
    _put("工作流执行完成\n" if not blocked else "工作流执行完成（有失败步骤）\n")
    _notify_task_done(wf.get('name', '未命名'))
    with _cancel_lock:
        _cancelled_tasks.discard(task_id)
    _put(None)
    time.sleep(10)
    _log_queues.pop(task_id, None)


@app.route("/api/workflow/open-update-wc", methods=["POST"])
def api_workflow_open_update_wc():
    data = request.get_json(force=True)
    prefixes = data.get("prefixes", [])
    if not prefixes:
        return jsonify({"error": "未提供路径前缀"}), 400

    tortoise = _get_tortoise_proc_path()
    if not tortoise:
        return jsonify({"error": "未找到 TortoiseSVN，请安装后重试"}), 400

    opened = []
    missing = []
    for prefix in prefixes:
        for subdir in ["Client", "gameData"]:
            d = os.path.join(prefix, subdir)
            if os.path.isdir(d):
                subprocess.Popen([tortoise, "/command:update", "/path:" + d])
                opened.append(d)
            else:
                missing.append(d)

    if not opened:
        return jsonify({"error": "未找到可更新的 Client 或 gameData 目录", "missing": missing}), 400
    return jsonify({"opened": opened, "missing": missing})


@app.route("/api/workflow/update-wc", methods=["POST"])
def api_workflow_update_wc():
    data = request.get_json(force=True)
    prefixes = data.get("prefixes", [])
    name = data.get("name", "工作流")
    if not prefixes:
        return jsonify({"error": "未提供路径前缀"}), 400
    task_id = _get_next_task_id()
    q = queue.Queue()
    _log_queues[task_id] = q
    threading.Thread(target=_workflow_update_wc_worker, args=(task_id, prefixes, name), daemon=True).start()
    return jsonify({"task_id": task_id})


def _workflow_update_wc_worker(task_id, prefixes, name):
    q = _log_queues.setdefault(task_id, queue.Queue())

    def _put(msg):
        q.put(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    try:
        svn = _get_svn_path()
        q.put(f"{'='*50}\n")
        q.put(f"🔄 更新工作流「{name}」的 SVN 工作副本\n")
        q.put(f"{'='*50}\n")
        dirs = []
        for prefix in prefixes:
            for subdir in ["Client", "gameData"]:
                d = os.path.join(prefix, subdir)
                if not os.path.isdir(d):
                    q.put(f"⏭ 目录不存在: {d}\n")
                else:
                    dirs.append(d)
        if not dirs:
            q.put("没有需要更新的目录\n")
            return
        q.put(f"共 {len(dirs)} 个目录，并行更新中...\n")
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(dirs)) as executor:
            fut_map = {executor.submit(_svn_update_with_cleanup, svn, d, _put, task_id, accept_mine=True): d for d in dirs}
            for fut in concurrent.futures.as_completed(fut_map):
                d = fut_map[fut]
                try:
                    results[d] = fut.result()
                except Exception as e:
                    results[d] = False
                    q.put(f"  ❌ 更新失败: {d} → {e}\n")
        success = sum(1 for v in results.values() if v)
        fail = sum(1 for v in results.values() if not v)
        q.put(f"\n{'='*50}\n")
        q.put(f"📊 更新完成: {success} 成功, {fail} 失败 (共 {len(dirs)} 个目录)\n")
    except Exception as e:
        q.put(f"\n❌ 更新任务异常终止: {e}\n")
    finally:
        _notify_task_done(f"更新Wc:{name}")
        q.put(None)
        _log_queues.pop(task_id, None)


@app.route("/api/workflow/run", methods=["POST"])
def api_workflow_run():
    data = request.get_json(force=True)
    wf_idx = data.get("wf_idx", -1)
    step_indices = data.get("step_indices", None)
    cfg = load_config()
    wfs = cfg.get("workflows", [])
    if wf_idx < 0 or wf_idx >= len(wfs):
        return jsonify({"error": "无效工作流"}), 400
    wf = wfs[wf_idx]
    steps = wf.get("steps", [])
    if not steps:
        return jsonify({"error": "工作流没有步骤"}), 400

    if step_indices is not None:
        filtered = []
        for si in step_indices:
            if 0 <= si < len(steps):
                filtered.append(steps[si])
        if not filtered:
            return jsonify({"error": "未选中有效步骤"}), 400
        steps = filtered

    task_id = _get_next_task_id()
    q = queue.Queue()
    _log_queues[task_id] = q
    threading.Thread(target=_run_wf_task, args=(q, wf, steps, task_id), daemon=True).start()
    return jsonify({"task_id": task_id})


def _exec_export_text(step, put, task_id=None):
    input_file = step.get("input_file", "").strip()
    if input_file and not os.path.exists(input_file):
        put(f"输入文件无效: {input_file}\n")
        return False

    input_dir = os.path.dirname(input_file) if input_file else ""
    put(f"输入文件: {os.path.basename(input_file) if input_file else 'N/A'}\n")

    bat_dir = input_dir
    bat_names = ["服务器文字表导出_替换文本引用.bat", "客户端文字表导出_替换文本引用.bat"]
    found_tools = []
    for name in bat_names:
        p = os.path.join(bat_dir, name)
        if os.path.isfile(p):
            found_tools.append(p)
            put(f"  发现工具: {name}\n")
        else:
            put(f"  未找到: {name}\n")

    if not found_tools:
        put("没有可执行的导出工具\n")
        return True

    svn = _get_svn_path()
    upload_svn_dirs = step.get("upload_svn_dir", [])
    if isinstance(upload_svn_dirs, str):
        upload_svn_dirs = [d.strip() for d in upload_svn_dirs.split(",") if d.strip()]
    for d in upload_svn_dirs:
        d = d.strip()
        if d and os.path.isdir(d):
            put(f"正在更新上传目录: {d}\n")
            _svn_update_with_cleanup(svn, d, put, task_id)
        elif d:
            put(f"上传SVN目录无效: {d}\n")

    if input_file and os.path.isfile(input_file):
        put(f"正在锁定主文件: {os.path.basename(input_file)}\n")
        if not _exec_lock_svn({"target_path": input_file, "lock_msg": "导出文字表前锁定", "update_dirs": []}, put, task_id):
            return False

    put(f"使用 {len(found_tools)} 个工具并行执行...\n")

    def _run_one(tool_path):
        put(f"  正在执行: {os.path.basename(tool_path)}\n")
        proc = subprocess.Popen(
            ["cmd.exe", "/c", tool_path],
            cwd=os.path.dirname(tool_path) if os.path.isdir(os.path.dirname(tool_path)) else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            **_get_bat_subprocess_kwargs())
        _register_proc(proc, task_id)
        try:
            # 后台线程读取 stderr，防止管道阻塞
            _stderr_lines = []
            def _read_stderr():
                for err_line in iter(proc.stderr.readline, b""):
                    _stderr_lines.append(err_line)
                proc.stderr.close()
            stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()

            for line in iter(proc.stdout.readline, b""):
                try:
                    raw = line.rstrip()
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = raw.decode("gbk", errors="replace")
                    put(f"    {text}\n")
                except Exception:
                    pass
            proc.wait(timeout=3600)
            stderr_thread.join(timeout=5)
            # 打印 stderr 内容（如果有）
            if _stderr_lines:
                put(f"  --- stderr 输出 ---\n")
                for err_line in _stderr_lines:
                    try:
                        raw = err_line.rstrip()
                        try:
                            text = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            text = raw.decode("gbk", errors="replace")
                        put(f"  [stderr] {text}\n")
                    except Exception:
                        pass
            if proc.returncode == 0:
                put(f"  {os.path.basename(tool_path)} 已完成\n")
            else:
                put(f"  {os.path.basename(tool_path)} 退出代码: {proc.returncode}\n")
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.communicate(timeout=5)
            except Exception:
                pass
            put(f"  {os.path.basename(tool_path)} 超时\n")
        except Exception as e:
            put(f"  {os.path.basename(tool_path)} 错误: {e}\n")
        finally:
            _unregister_proc(proc, task_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(found_tools)) as executor:
        futures = [executor.submit(_run_one, t) for t in found_tools]
        concurrent.futures.wait(futures)

    # 导出成功后，如果有配置上传SVN目录，执行上传
    if upload_svn_dirs:
        put(f"\n导出完成，执行上传\n")
        _exec_upload_svn({"dirs": upload_svn_dirs}, put, task_id)

    return True


def _get_tortoise_proc_path():
    """查找 TortoiseProc.exe"""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\TortoiseSVN") as key:
            path, _ = winreg.QueryValueEx(key, "ProcPath")
            if path and os.path.exists(path):
                return path
    except (OSError, FileNotFoundError):
        pass
    candidates = [
        r"C:\Program Files\TortoiseSVN\bin\TortoiseProc.exe",
        r"C:\Program Files (x86)\TortoiseSVN\bin\TortoiseProc.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _exec_upload_svn(step, put, task_id=None):
    dirs = step.get("dirs", [])
    if not dirs:
        put("未配置上传目录\n")
        return True

    tortoise = _get_tortoise_proc_path()
    if not tortoise:
        put("未找到 TortoiseSVN，无法提交。请安装 TortoiseSVN 后重试\n")
        return False

    for d in dirs:
        d = d.strip()
        if not os.path.exists(d):
            put(f"路径不存在: {d}\n")
            continue
        if os.path.isfile(d):
            d = os.path.dirname(d)

        put(f"打开 TortoiseSVN 提交对话框: {d}\n")
        try:
            subprocess.Popen([tortoise, "/command:commit", "/path:" + d])
        except Exception as e:
            put("TortoiseSVN 启动失败: " + str(e) + "\n")
            return False
    return True


def _exec_copy_files(step, put, task_id=None):
    """整合文字表 — 自动检测文件→svn update→复制→lock→导出→上传"""
    src_dir = step.get("src_dir", "").strip()
    tgt_dir = step.get("tgt_dir", "").strip()
    if not src_dir or not os.path.isdir(src_dir):
        put(f"源目录无效: {src_dir}\n")
        return False
    if not tgt_dir or not os.path.isdir(tgt_dir):
        put(f"目标目录无效: {tgt_dir}\n")
        return False

    put(f"{'='*50}\n")
    put(f"整合文字表\n")
    put(f"源目录: {src_dir}\n")
    put(f"目标目录: {tgt_dir}\n\n")

    # ── 1. 自动检测源文件 ──
    src_text_dir = src_dir if os.path.basename(src_dir).lower() == "text" else os.path.join(src_dir, "Text")
    file_names = ["文字引用处理.xlsm", "Texts.xlsm"]
    found_files = []
    for fn in file_names:
        fp = os.path.join(src_text_dir, fn)
        if os.path.isfile(fp):
            found_files.append(fp)
            put(f"  发现文件: {fn}\n")
        else:
            put(f"  未找到: {fn}\n")
    if not found_files:
        put("没有需要复制的文件\n")
        return True

    # ── 2. 提取基础路径 ──
    base_path = os.path.dirname(tgt_dir)  # F:\D3_KR2_DEV\gameData → F:\D3_KR2_DEV
    svn = _get_svn_path()

    # ── 3. svn update（先更新源和目标到最新，再复制） ──
    put("正在更新源目录的 gameData...\n")
    _find_and_update_gamedata(src_dir, put, task_id)

    # ── 3b. 回退源目录中要复制的文件到最新版本，确保没有本地修改 ──
    put("回退源文件到 SVN 最新版本...\n")
    for fp in found_files:
        try:
            r = subprocess.run([svn, "revert", fp],
                               capture_output=True, text=True,
                               timeout=30, **_get_subprocess_kwargs())
            if r.returncode == 0:
                put(f"  ✓ {os.path.basename(fp)}\n")
            else:
                put(f"  ⚠ {os.path.basename(fp)}: {r.stderr.strip()[-100:]}\n")
        except Exception as e:
            put(f"  ⚠ {os.path.basename(fp)} 回退异常: {e}\n")
            if "系统找不到指定的文件" in str(e):
                put("  💡 " + _diagnose_svn_missing().replace("\n", "\n     ") + "\n")
                put("  → 正在自动安装 SVN 命令行工具...\n")
                ok, msg = _auto_install_svn_cli(put=lambda m: put("     " + m))
                put(f"  → {msg}\n")

    upload_paths = [
        os.path.join(base_path, "Client", "Assets", "StreamingAssets"),
        os.path.join(base_path, "gameData"),
    ]
    for up in upload_paths:
        if os.path.isdir(up):
            put(f"正在更新: {up}\n")
            _svn_update_with_cleanup(svn, up, put, task_id)
        else:
            put(f"路径不存在，跳过更新: {up}\n")

    # ── 4. 复制文件到目标目录 ──
    put("开始复制...\n")
    for fp in found_files:
        dst = os.path.join(tgt_dir, "Text", os.path.basename(fp))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            _copy2_force(fp, dst)
            put(f"  ✓ {os.path.basename(fp)}\n")
        except Exception as e:
            put(f"  ✗ {os.path.basename(fp)}: {e}\n")

    # ── 5. svn lock ──
    lock_file = os.path.join(base_path, "gameData", "Text", "Texts.xlsm")
    if os.path.isfile(lock_file):
        put(f"正在锁定: Texts.xlsm\n")
        if not _exec_lock_svn({"target_path": lock_file, "lock_msg": "整合文字表前锁定", "update_dirs": []}, put, task_id):
            return False
    else:
        put(f"锁定文件不存在: {lock_file}\n")

    # ── 6. 导出工具 ──
    bat_dir = os.path.join(base_path, "gameData", "Text")
    bat_names = ["服务器文字表导出_替换文本引用.bat", "客户端文字表导出_替换文本引用.bat"]
    found_bats = []
    for name in bat_names:
        p = os.path.join(bat_dir, name)
        if os.path.isfile(p):
            found_bats.append(p)
            put(f"  发现导出工具: {name}\n")
        else:
            put(f"  未找到导出工具: {name}\n")

    if found_bats:
        put(f"使用 {len(found_bats)} 个导出工具并行执行...\n")

        def _run_one(tool_path):
            put(f"  正在执行: {os.path.basename(tool_path)}\n")
            proc = subprocess.Popen(
                ["cmd.exe", "/c", tool_path],
                cwd=os.path.dirname(tool_path),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                **_get_bat_subprocess_kwargs())
            _register_proc(proc, task_id)
            try:
                # 后台线程读取 stderr，防止管道阻塞
                _stderr_lines = []
                def _read_stderr():
                    for err_line in iter(proc.stderr.readline, b""):
                        _stderr_lines.append(err_line)
                    proc.stderr.close()
                stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
                stderr_thread.start()

                for line in iter(proc.stdout.readline, b""):
                    try:
                        raw = line.rstrip()
                        try:
                            text = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            text = raw.decode("gbk", errors="replace")
                        put(f"    {text}\n")
                    except Exception:
                        pass
                proc.wait(timeout=3600)
                stderr_thread.join(timeout=5)
                # 打印 stderr 内容（如果有）
                if _stderr_lines:
                    put(f"  --- stderr 输出 ---\n")
                    for err_line in _stderr_lines:
                        try:
                            raw = err_line.rstrip()
                            try:
                                text = raw.decode("utf-8")
                            except UnicodeDecodeError:
                                text = raw.decode("gbk", errors="replace")
                            put(f"  [stderr] {text}\n")
                        except Exception:
                            pass
                if proc.returncode == 0:
                    put(f"  {os.path.basename(tool_path)} 已完成\n")
                else:
                    put(f"  {os.path.basename(tool_path)} 退出代码: {proc.returncode}\n")
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.communicate(timeout=5)
                except Exception:
                    pass
                put(f"  {os.path.basename(tool_path)} 超时\n")
            except Exception as e:
                put(f"  {os.path.basename(tool_path)} 错误: {e}\n")
            finally:
                _unregister_proc(proc, task_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(found_bats)) as executor:
            futures = [executor.submit(_run_one, t) for t in found_bats]
            concurrent.futures.wait(futures)

    # ── 7. 上传 ──
    valid_upload = [up for up in upload_paths if os.path.isdir(up)]
    if valid_upload:
        put(f"\n导出完成，执行上传\n")
        _exec_upload_svn({"dirs": valid_upload}, put, task_id)

    return True


def _svn_update_with_cleanup(svn, d, put, task_id, accept_mine=False):  # noqa: C901
    """执行 svn update，遇到 E155004/E155037 时自动 cleanup 重试一次"""
    accept_flag = "mine-full" if accept_mine else "theirs-full"
    proc = None
    try:
        proc = subprocess.Popen([svn, "update", "--accept", accept_flag, d],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                **_get_subprocess_kwargs())
        _register_proc(proc, task_id)
        try:
            out_bytes, err_bytes = proc.communicate(timeout=120)
            stdout = _svn_decode_output(out_bytes)
            stderr = _svn_decode_output(err_bytes)
            if proc.returncode == 0:
                for line in stdout.strip().splitlines():
                    line = line.strip()
                    if line:
                        put(f"  {line}\n")
                if accept_mine:
                    cfiles = [l[2:].strip() for l in stdout.splitlines()
                              if l.strip().startswith("C ") and not l.strip().startswith(("C Summary","C Text","C Property"))]
                    cfiles = [f for f in cfiles if f]
                    if cfiles:
                        put(f"  ⚠ 以下 {len(cfiles)} 个文件存在冲突，已自动保留本地版本:\n")
                        for cf in cfiles:
                            put(f"    - {cf}\n")
                put(f"更新完成: {d}\n")
                return True
            err = stderr.strip()
            if "E155004" in err or "E155037" in err:
                put("检测到 SVN 锁，正在执行 cleanup...\n")
                cleanup_proc = subprocess.Popen(
                    [svn, "cleanup", d],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    **_get_subprocess_kwargs())
                _register_proc(cleanup_proc, task_id)
                try:
                    cl_out, cl_err = cleanup_proc.communicate(timeout=60)
                    cl_stdout = _svn_decode_output(cl_out)
                    cl_stderr = _svn_decode_output(cl_err)
                    for line in cl_stdout.strip().splitlines():
                        line = line.strip()
                        if line:
                            put(f"  [cleanup] {line}\n")
                    if cleanup_proc.returncode != 0:
                        put(f"  cleanup 失败 ({cleanup_proc.returncode}): {cl_stderr.strip()[-200:]}\n")
                        put(f"  正在重试 svn cleanup（无参数模式）...\n")
                        cl2 = subprocess.Popen(
                            [svn, "cleanup", d, "--remove-unversioned"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            **_get_subprocess_kwargs())
                        _register_proc(cl2, task_id)
                        try:
                            cl2.communicate(timeout=60)
                        finally:
                            _unregister_proc(cl2, task_id)
                        if cl2.returncode != 0:
                            put(f"  cleanup 重试仍失败，尝试强制回退本地修改...\n")
                            revert_proc = subprocess.Popen(
                                [svn, "revert", "-R", d],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                **_get_subprocess_kwargs())
                            _register_proc(revert_proc, task_id)
                            try:
                                revert_proc.communicate(timeout=60)
                            finally:
                                _unregister_proc(revert_proc, task_id)
                            put(f"  本地回退完成，重试更新...\n")
                finally:
                    _unregister_proc(cleanup_proc, task_id)
                put("cleanup 完成，重试更新...\n")
                retry_proc = subprocess.Popen(
                    [svn, "update", "--accept", accept_flag, d],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    **_get_subprocess_kwargs())
                _register_proc(retry_proc, task_id)
                try:
                    retry_out, retry_err = retry_proc.communicate(timeout=120)
                    retry_stdout = _svn_decode_output(retry_out)
                    retry_stderr = _svn_decode_output(retry_err)
                    if retry_proc.returncode == 0:
                        for line in retry_stdout.strip().splitlines():
                            line = line.strip()
                            if line:
                                put(f"  {line}\n")
                        if accept_mine:
                            cfiles = [l[2:].strip() for l in retry_stdout.splitlines()
                                      if l.strip().startswith("C ") and not l.strip().startswith(("C Summary","C Text","C Property"))]
                            cfiles = [f for f in cfiles if f]
                            if cfiles:
                                put(f"  ⚠ 以下 {len(cfiles)} 个文件存在冲突，已自动保留本地版本:\n")
                                for cf in cfiles:
                                    put(f"    - {cf}\n")
                        put(f"更新完成: {d}\n")
                        return True
                    put(f"cleanup 后更新仍失败: {d} - {retry_stderr[-200:]}\n")
                    return False
                finally:
                    _unregister_proc(retry_proc, task_id)
            else:
                put(f"更新失败: {d} - {err[-200:]}\n")
                return False
        finally:
            _unregister_proc(proc, task_id)
    except subprocess.TimeoutExpired:
        if proc:
            _unregister_proc(proc, task_id)
        put(f"更新超时: {d}\n")
        return False
    except Exception as e:
        if proc:
            _unregister_proc(proc, task_id)
        put(f"更新异常: {e}\n")
        if "系统找不到指定的文件" in str(e):
            put("  💡 " + _diagnose_svn_missing().replace("\n", "\n     ") + "\n")
            put("  → 正在自动安装 SVN 命令行工具...\n")
            ok, msg = _auto_install_svn_cli(put=lambda m: put("     " + m))
            put(f"  → {msg}\n")
        return False


def _get_svn_cached_user():
    """从 SVN 凭据缓存读取当前认证用户名"""
    try:
        auth_dir = os.path.join(os.environ.get('APPDATA', ''), 'Subversion', 'auth', 'svn.simple')
        if not os.path.isdir(auth_dir):
            return None
        for fname in os.listdir(auth_dir):
            fpath = os.path.join(auth_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.strip() == 'username' and i + 1 < len(lines):
                        val_line = lines[i + 1]
                        if val_line.startswith('V '):
                            parts = val_line.split(' ', 1)
                            val_len = int(parts[1].strip()) if len(parts) > 1 else 0
                            if val_len > 0 and i + 2 < len(lines):
                                raw = lines[i + 2].strip()
                                return raw[:val_len]
            except Exception:
                continue
    except Exception:
        pass
    return None


def _merge_error_code_resolve_lang(path):
    """从路径中自动找到 gameData\\Language 目录"""
    path = os.path.abspath(path)
    if path.endswith("Language") and os.path.isdir(path):
        return path
    test = os.path.join(path, "Language")
    if os.path.isdir(test):
        return test
    test = os.path.join(path, "gameData", "Language")
    if os.path.isdir(test):
        return test
    return None


def _exec_merge_error_code(step, put, task_id=None):
    """整合错误码：复制每个语言目录的 Data2\\ErrorMessage.xlsm"""
    src_path = step.get("src_path", "").strip()
    tgt_path = step.get("tgt_path", "").strip()
    if not src_path:
        put("未指定源路径\n"); return False
    if not tgt_path:
        put("未指定目标路径\n"); return False

    put(f"{'='*50}\n")
    put("整合错误码\n")
    put(f"源路径: {src_path}\n")
    put(f"目标路径: {tgt_path}\n\n")

    src_lang = _merge_error_code_resolve_lang(src_path)
    if not src_lang:
        put("无法在源路径找到 gameData\\Language 目录\n"); return False
    tgt_lang = _merge_error_code_resolve_lang(tgt_path)
    if not tgt_lang:
        put("无法在目标路径找到 gameData\\Language 目录\n"); return False

    put(f"源 Language: {src_lang}\n")
    put(f"目标 Language: {tgt_lang}\n\n")

    # 更新来源和目标 SVN 目录
    svn = _get_svn_path()
    src_gamedata = os.path.dirname(src_lang)
    tgt_gamedata = os.path.dirname(tgt_lang)
    tgt_base = os.path.dirname(tgt_gamedata)
    tgt_streaming = os.path.join(tgt_base, "Client", "Assets", "StreamingAssets")

    for label, d in [("来源 gameData", src_gamedata), ("目标 gameData", tgt_gamedata),
                     ("目标 StreamingAssets", tgt_streaming)]:
        if os.path.isdir(d):
            put(f"正在更新 {label}: {d}\n")
            _svn_update_with_cleanup(svn, d, put, task_id)
        else:
            put(f"路径不存在，跳过更新 {label}: {d}\n")

    # 遍历源语言目录，复制 ErrorMessage.xlsm
    put("\n开始复制...\n")
    copied = 0
    for code in sorted(os.listdir(src_lang)):
        src_sub = os.path.join(src_lang, code)
        if not os.path.isdir(src_sub):
            continue
        src_file = os.path.join(src_sub, "Data2", "ErrorMessage.xlsm")
        if not os.path.isfile(src_file):
            continue
        tgt_sub = os.path.join(tgt_lang, code)
        tgt_file = os.path.join(tgt_sub, "Data2", "ErrorMessage.xlsm")
        try:
            os.makedirs(os.path.dirname(tgt_file), exist_ok=True)
            _copy2_force(src_file, tgt_file)
            put(f"  ✓ [{code}] ErrorMessage.xlsm\n")
            copied += 1
        except Exception as e:
            put(f"  ✗ [{code}] 复制失败: {e}\n")

    put(f"\n共复制 {copied} 个文件\n")

    if copied == 0:
        put("没有需要导出的文件\n")
        return True

    # 语言代码：优先用设置的，否则自动从目录识别
    raw_codes = (step.get("lang_codes") or "").strip()
    if raw_codes:
        codes = [c.strip() for c in raw_codes.split(",") if c.strip()]
        put(f"使用指定的语言代码: {', '.join(codes)}\n")
    else:
        codes = []
        for code in sorted(os.listdir(tgt_lang)):
            tgt_sub = os.path.join(tgt_lang, code)
            if os.path.isdir(tgt_sub) and os.path.isfile(os.path.join(tgt_sub, "Data2", "ErrorMessage.xlsm")):
                codes.append(code)
        put(f"自动识别语言: {', '.join(codes)}\n")

    put("开始执行导出错误码流程...\n\n")
    export_ok = _exec_export_error_code({
        "root_dir": tgt_gamedata,
        "lang_codes": ",".join(codes),
        "upload_svn_dir": [tgt_gamedata, tgt_streaming],
    }, put, task_id)

    return export_ok


def _exec_lock_svn(step, put, task_id=None):
    target_path = step.get("target_path", "").strip()
    lock_msg = step.get("lock_msg", "锁定中，请勿修改")
    if not target_path or not os.path.isfile(target_path):
        put(f"锁定目标无效: {target_path}\n")
        return False
    svn = _get_svn_path()
    put(f"SVN 锁定: {target_path}\n")

    update_dirs = step.get("update_dirs", [])
    if update_dirs:
        for d in update_dirs:
            d = d.strip()
            if not d or not os.path.isdir(d):
                put(f"更新目录无效: {d}\n")
                return False
            put(f"正在更新目录: {d}\n")
            if not _svn_update_with_cleanup(svn, d, put, task_id):
                return False

    proc = None
    try:
        proc = subprocess.Popen([svn, "lock", "-m", lock_msg, target_path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                **_get_subprocess_kwargs())
        _register_proc(proc, task_id)
        try:
            out_bytes, err_bytes = proc.communicate(timeout=60)
            stdout = _svn_decode_output(out_bytes)
            stderr = _svn_decode_output(err_bytes)
            if proc.returncode == 0:
                put("锁定成功\n")
                return True
            else:
                # 从错误信息解析锁主，与 SVN 凭据缓存的实际用户比对
                m = re.search(r"locked by user '([^']+)'", stderr)
                lock_owner = m.group(1) if m else ""
                cached_user = _get_svn_cached_user()
                if lock_owner:
                    if cached_user and lock_owner == cached_user:
                        put("文件已由本人锁定，继续执行\n")
                        return True
                    else:
                        put(f"锁定失败，被 '{lock_owner}' 锁定（当前凭据用户: {cached_user or '?'}）\n")
                else:
                    put(f"锁定失败: {stderr[-200:]}\n")
        finally:
            _unregister_proc(proc, task_id)
    except Exception as e:
        if proc:
            _unregister_proc(proc, task_id)
        put(f"锁定异常: {e}\n")
        if "系统找不到指定的文件" in str(e):
            put("  💡 " + _diagnose_svn_missing().replace("\n", "\n     ") + "\n")
            put("  → 正在自动安装 SVN 命令行工具...\n")
            ok, msg = _auto_install_svn_cli(put=lambda m: put("     " + m))
            put(f"  → {msg}\n")
    return False


def _exec_unlock_svn(step, put, task_id=None):
    target_path = step.get("target_path", "").strip()
    if not target_path or not os.path.isfile(target_path):
        put(f"解锁目标无效: {target_path}\n")
        return False
    svn = _get_svn_path()
    put(f"SVN 解锁: {target_path}\n")

    update_dirs = step.get("update_dirs", [])
    if update_dirs:
        for d in update_dirs:
            d = d.strip()
            if not d or not os.path.isdir(d):
                put(f"更新目录无效: {d}\n")
                return False
            put(f"正在更新目录: {d}\n")
            if not _svn_update_with_cleanup(svn, d, put, task_id):
                return False

    proc = None
    try:
        proc = subprocess.Popen([svn, "unlock", target_path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                **_get_subprocess_kwargs())
        _register_proc(proc, task_id)
        try:
            out_bytes, err_bytes = proc.communicate(timeout=60)
            stdout = _svn_decode_output(out_bytes)
            stderr = _svn_decode_output(err_bytes)
            if proc.returncode == 0:
                put("解锁成功\n")
                return True
            else:
                put(f"解锁失败: {stderr[-200:]}\n")
        finally:
            _unregister_proc(proc, task_id)
    except Exception as e:
        if proc:
            _unregister_proc(proc, task_id)
        put(f"解锁异常: {e}\n")
    return True


def _exec_open_tables(step, put, task_id=None):
    file_paths = step.get("file_paths", [])
    if not file_paths:
        put("没有要打开的文件\n")
        return True
    for fp in file_paths:
        fp = fp.strip()
        if not fp or not os.path.exists(fp):
            put(f"文件不存在: {fp}\n")
            continue
        # 打开前更新 gameData 目录并锁定文件
        _find_and_update_gamedata(fp, put, task_id)
        if not _exec_lock_svn({"target_path": fp, "lock_msg": "打开表格前锁定", "update_dirs": []}, put, task_id):
            continue
        try:
            os.startfile(fp)
            put(f"打开: {os.path.basename(fp)}\n")
        except Exception as e:
            put(f"无法打开 {fp}: {e}\n")
    return True


def _svn_decode_output(data):
    try:
        return data.decode("gbk")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _exec_revert_svn(step, put, task_id=None):
    target_paths = []
    rp = step.get("revert_paths", [])
    if isinstance(rp, list) and rp:
        target_paths = [p.strip() for p in rp if p.strip()]

    valid_paths = [p for p in target_paths if os.path.exists(p)]
    if not valid_paths:
        put("没有有效的回退路径\n")
        return False

    svn = _get_svn_path()
    all_ok = True

    for target_path in valid_paths:
        ok = _revert_one_path(svn, target_path, step, put, task_id)
        if not ok:
            all_ok = False

    put("SVN 回退完成\n")
    return all_ok


def _revert_one_path(svn, target_path, step, put, task_id):
    put(f"{'='*50}\n")
    put(f"SVN回退: {target_path}\n")

    # 先 cleanup 确保无残留锁
    put("正在 cleanup 工作副本...\n")
    try:
        subprocess.run([svn, "cleanup", target_path],
                       capture_output=True, timeout=60,
                       **_get_subprocess_kwargs())
    except Exception:
        pass

    # 更新到服务器最新版本
    put("正在更新工作副本至最新版本...\n")
    _svn_update_with_cleanup(svn, target_path, put, task_id)

    # 解析排除路径
    raw_exclude = step.get("exclude_paths", [])
    if isinstance(raw_exclude, str):
        exclude_paths = [e.strip() for e in raw_exclude.split(",") if e.strip()]
    else:
        exclude_paths = [e.strip() for e in raw_exclude if e.strip()]

    # 直接将排除路径解析为实际文件/目录路径
    excluded_files = []
    for excl in exclude_paths:
        excl_norm = excl.replace("/", os.sep).replace("\\", os.sep)
        candidate = excl_norm if os.path.isabs(excl_norm) else os.path.join(target_path, excl_norm)
        if os.path.exists(candidate):
            excluded_files.append(os.path.normpath(candidate))
    if excluded_files:
        put(f"排除 {len(excluded_files)} 个文件/目录\n")

    tmpdir = None
    try:
        if excluded_files:
            tmpdir = tempfile.mkdtemp(prefix="svn_revert_bak_")
            put("正在备份排除的文件到临时目录...\n")
            for fp in excluded_files:
                rel = os.path.relpath(fp, target_path)
                dest = os.path.join(tmpdir, rel)
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    if os.path.isdir(fp):
                        shutil.copytree(fp, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(fp, dest)
                except Exception as e:
                    put(f"  ⚠ 备份失败（跳过排除）: {rel} - {e}\n")

        put("正在全量回退本地所有修改...\n")

        r = subprocess.run(
            [svn, "revert", "-R", target_path],
            capture_output=True, timeout=120,
            **_get_subprocess_kwargs())
        if r.returncode != 0:
            err = _svn_decode_output(r.stderr)[:200] if r.stderr else ""
            put(f"全量回退异常: {err}\n")
            return False

        if excluded_files and tmpdir:
            put("正在恢复排除的文件...\n")
            for fp in excluded_files:
                rel = os.path.relpath(fp, target_path)
                src = os.path.join(tmpdir, rel)
                if not os.path.exists(src):
                    continue
                try:
                    if os.path.isdir(src):
                        if os.path.exists(fp):
                            shutil.rmtree(fp)
                        shutil.copytree(src, fp)
                    else:
                        os.makedirs(os.path.dirname(fp), exist_ok=True)
                        shutil.copy2(src, fp)
                except Exception as e:
                    put(f"  ⚠ 恢复失败: {rel} - {e}\n")
            put("排除文件恢复完成\n")
    finally:
        if tmpdir:
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    # 删除未版本控制的文件
    if step.get("delete_unversioned"):
        put("正在扫描未版本控制文件...\n")
        excluded_set = set(os.path.normpath(f) for f in excluded_files)
        try:
            r_status = subprocess.run(
                [svn, "status", "--no-ignore", target_path],
                capture_output=True, timeout=60,
                **_get_subprocess_kwargs()
            )
            if r_status.returncode == 0:
                unversioned = []
                for line in _svn_decode_output(r_status.stdout).splitlines():
                    if len(line) < 8 or line[0] != "?":
                        continue
                    p = line[7:].strip()
                    if not os.path.isabs(p):
                        p = os.path.join(target_path, p)
                    p = os.path.normpath(p)
                    if p not in excluded_set:
                        unversioned.append(p)
                if unversioned:
                    put(f"正在删除 {len(unversioned)} 个未版本控制文件...\n")
                    deleted = 0
                    for fp in unversioned:
                        try:
                            if os.path.isdir(fp):
                                shutil.rmtree(fp, ignore_errors=True)
                            else:
                                os.remove(fp)
                            deleted += 1
                        except Exception:
                            pass
                    put(f"  已删除 {deleted} 个文件\n")
                else:
                    put("  没有未版本控制的文件\n")
        except Exception as e:
            put(f"  ⚠ 扫描未版本文件失败: {e}\n")

    put("清理根目录残留属性...\n")
    subprocess.run(
        [svn, "revert", target_path, "--depth", "empty"],
        capture_output=True, timeout=30,
        **_get_subprocess_kwargs())

    put("SVN 回退完成\n")
    return True


def _find_and_update_gamedata(file_path, put, task_id):
    """从文件路径逐级向上找 gameData 目录，执行 svn update（冲突全量覆盖）"""
    d = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path
    while d and len(d) > 3:
        if os.path.basename(d).lower() == "gamedata":
            svn = _get_svn_path()
            put(f"正在更新原文件SVN目录: {d}\n")
            _svn_update_with_cleanup(svn, d, put, task_id)
            return
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    put(f"未找到 gameData 目录，跳过更新\n")


def _exec_export_error_code(step, put, task_id=None):
    root_dir = step.get("root_dir", "").strip()
    lang_codes = step.get("lang_codes", "").strip()
    if not root_dir:
        put("未指定根目录\n")
        return False
    if not lang_codes:
        put("未指定语言列表\n")
        return False

    def _resolve_language_dir(base):
        base = os.path.abspath(base)
        if base.endswith("Language") and os.path.isdir(base):
            return base
        test = os.path.join(base, "Language")
        if os.path.isdir(test):
            return test
        test = os.path.join(base, "gameData", "Language")
        if os.path.isdir(test):
            return test
        return None

    lang_dir = _resolve_language_dir(root_dir)
    if not lang_dir:
        put("无法找到 gameData\\Language 目录: " + root_dir + "\n")
        return False

    codes = [c.strip() for c in lang_codes.split(",") if c.strip()]
    if not codes:
        put("语言列表为空\n")
        return False

    put("Language 目录: " + lang_dir + "\n")
    put("处理语言: " + ", ".join(codes) + "\n")

    # ── 导出前更新配置的上传SVN目录 ──
    upload_svn_dirs = step.get("upload_svn_dir", [])
    if isinstance(upload_svn_dirs, str):
        upload_svn_dirs = [d.strip() for d in upload_svn_dirs.split(",") if d.strip()]
    if upload_svn_dirs:
        svn = _get_svn_path()
        for d in upload_svn_dirs:
            d = d.strip()
            if d and os.path.isdir(d):
                put(f"正在更新上传目录: {d}\n")
                _svn_update_with_cleanup(svn, d, put, task_id)

    import subprocess as _sp
    script_dir = os.path.dirname(os.path.abspath(__file__))
    erl_script = os.path.join(script_dir, "..", "_export_error_code_erl.py")
    py_exe = sys.executable
    # 子进程需要能找到 py_modules 里的依赖（如 openpyxl）
    _pm_path = os.path.join(script_dir, "py_modules")
    _erl_env = {**os.environ, "PYTHONPATH": _pm_path} if os.path.isdir(_pm_path) else None

    results = []

    for code in codes:
        lang_path = os.path.join(lang_dir, code)
        put("  [" + code + "] " + lang_path + "\n")

        xlsm_file = os.path.join(lang_path, "Data2", "ErrorMessage.xlsm")
        if not os.path.isfile(xlsm_file):
            put("  [" + code + "] 缺少: Data2\\ErrorMessage.xlsm\n")
            results.append((code, False, "xlsm 未找到"))
            continue

        batch_file = os.path.join(lang_path, "客户端单个导出2.bat")
        config_bat = os.path.join(lang_path, "config.bat")
        make_exe = os.path.join(lang_path, "protobuf", "make_gamedata_exe.bat")
        make_ready = os.path.join(lang_path, "protobuf", "make_ready.bat")

        checks = [
            (batch_file, "客户端单个导出2.bat"),
            (config_bat, "config.bat"),
            (make_exe, "protobuf\\make_gamedata_exe.bat"),
            (make_ready, "protobuf\\make_ready.bat"),
        ]

        if os.path.isfile(make_exe):
            exe_content = open(make_exe, "r", encoding="utf-8", errors="replace").read()
            if "ExportXlsmToPB.py" in exe_content:
                export_py = os.path.join(lang_path, "protobuf", "ExportXlsmToPB.py")
                protoc = os.path.join(lang_path, "protobuf", "proto", "protoc.exe")
                proto_init = os.path.join(lang_path, "protobuf", "proto", "__init__.py")
                checks += [
                    (export_py, "protobuf\\ExportXlsmToPB.py"),
                    (protoc, "protobuf\\proto\\protoc.exe"),
                    (proto_init, "protobuf\\proto\\__init__.py"),
                    (r"C:\Python27\python.exe", "Python 2.7 (C:\\Python27\\python.exe)"),
                ]
                base_pb = os.path.join(lang_path, "protobuf", "proto", "Base.pb")
                base_pb2 = os.path.join(lang_path, "protobuf", "proto", "Base_pb2.py")
                if not os.path.isfile(base_pb) and not os.path.isfile(base_pb2):
                    checks.append((base_pb, "protobuf\\proto\\Base.pb 或 Base_pb2.py"))
            elif "CompressExport.exe" in exe_content:
                compress_exe = os.path.join(lang_path, "protobuf", "CompressExport.exe")
                checks.append((compress_exe, "protobuf\\CompressExport.exe"))

        missing = [name for path, name in checks if not os.path.exists(path)]
        if missing:
            put("  [" + code + "] 缺少源工具文件: " + ", ".join(missing) + "\n")
            results.append((code, False, "缺少源工具文件"))
            continue

        ok = True

        put("  [" + code + "] 客户端导出...\n")
        try:
            import tempfile, shutil
            proto_dir = os.path.join(lang_path, "protobuf")
            proto_out = os.path.join(proto_dir, "proto", "out")
            # 检测分支类型：Asia 的 __init__.py 含 from importlib import reload（Python3）
            _py3_init = False
            _init_py = os.path.join(proto_dir, "proto", "__init__.py")
            if os.path.isfile(_init_py):
                with open(_init_py, "r", encoding="utf-8", errors="replace") as _f:
                    if "from importlib import reload" in _f.read():
                        _py3_init = True
            _bf = os.path.join(tempfile.gettempdir(), "_xy_export_" + str(os.getpid()) + ".bat")
            with open(_bf, "w", newline="") as _f:
                _f.write('@echo off\r\n')
                _f.write(f'cd /d "{lang_path}"\r\n')
                _f.write(f'call "{os.path.join(lang_path, "config.bat")}"\r\n')
                _f.write(f'cd %MASTER_DATA%\r\ncd protobuf\r\n')
                if _py3_init:
                    # Asia：走完整工具链（make_gamedata_exe.bat 含 make_ready+ExportXlsmToPB）
                    _f.write(f'call "{os.path.join(lang_path, "protobuf", "make_gamedata_exe.bat")}" "{xlsm_file}"\r\n')
                else:
                    # KR2：跳过 make_gamedata_exe.bat，避免 make_ready.bat 删额外文件
                    _f.write('xcopy /y "proto\\*.py" "proto\\out\\" 2>nul\r\n')
                    _f.write('xcopy /y "proto\\*.pb" "proto\\out\\" 2>nul\r\n')
                    _f.write(f'call "%PYTHON_PATH%\\python.exe" "ExportXlsmToPB.py" "{xlsm_file}"\r\n')
            _env = {"PATH": r"C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem;C:\Python27;C:\Python27\DLLs",
                    "COMSPEC": r"C:\Windows\System32\cmd.exe",
                    "SYSTEMROOT": r"C:\Windows",
                    "TEMP": tempfile.gettempdir(), "TMP": tempfile.gettempdir(),
                    "USERPROFILE": os.environ.get("USERPROFILE", r"C:\Users\admin")}
            r_bat = _sp.run(["cmd", "/c", _bf], capture_output=True, timeout=300, env=_env, **_get_subprocess_kwargs())
            try:
                os.unlink(_bf)
            except Exception:
                pass
            copied = 0
            if r_bat.returncode == 0 and os.path.isdir(proto_out):
                proj_dir = os.path.normpath(os.path.join(lang_path, "..", "..", ".."))
                lang_name = os.path.basename(lang_path)
                for fn in os.listdir(proto_out):
                    fl = fn.lower()
                    if not os.path.isfile(os.path.join(proto_out, fn)) or fl == "base.pb" or fl.startswith("base_"):
                        continue
                    d = None
                    if fl.endswith(".bin"):
                        d = os.path.join(proj_dir, "client", "Assets", "StreamingAssets", "Language", lang_name, "BinData", "bin")
                    elif fl.endswith(".pb"):
                        d = os.path.join(proj_dir, "client", "Assets", "StreamingAssets", "Language", lang_name, "BinData", "pb")
                    elif fl.endswith(".txt"):
                        d = os.path.join(lang_path, "ExportTxt")
                    if d:
                        os.makedirs(d, exist_ok=True)
                        shutil.copy2(os.path.join(proto_out, fn), os.path.join(d, fn))
                        put("    " + fn + "\n")
                        copied += 1
            if copied > 0:
                put("  [" + code + "] 客户端导出成功\n")
            else:
                put("  [" + code + "] 客户端导出失败\n")
                if r_bat.returncode != 0:
                    _err = (r_bat.stderr or r_bat.stdout or b"").decode("gbk", errors="replace").strip()[:2000]
                    put("  [" + code + "] 错误:\n")
                    for _l in _err.split("\n"):
                        put("    |" + _l.rstrip() + "\n")
                ok = False
        except Exception as e:
            put("  [" + code + "] 客户端导出异常: " + str(e) + "\n")
            ok = False

        if ok:
            put("  [" + code + "] 服务端导出(erlang)...\n")
            try:
                r = _sp.run(
                    [py_exe, erl_script, "--xlsm", xlsm_file, "--lang-dir", lang_path],
                    capture_output=True,
                    encoding=locale.getpreferredencoding(), errors="replace",
                    timeout=60, env=_erl_env,
                    **_get_subprocess_kwargs()
                )
                if r.returncode == 0:
                    for line in (r.stdout or "").strip().split("\n"):
                        put("    " + line.strip() + "\n")
                    put("  [" + code + "] erlang 导出成功\n")
                else:
                    err = (r.stderr or r.stdout or "").strip()[:1000]
                    put("  [" + code + "] erlang 导出失败: " + err + "\n")
                    ok = False
            except Exception as e:
                put("  [" + code + "] erlang 导出异常: " + str(e) + "\n")
                ok = False

        results.append((code, ok, "成功" if ok else "失败"))
        if ok:
            put("  [" + code + "] 全部导出成功\n")
        else:
            put("  [" + code + "] 导出失败\n")

    ok_count = sum(1 for _, ok, _ in results if ok)
    put("导出错误码完成: " + str(ok_count) + "/" + str(len(codes)) + "\n")
    if ok_count == len(codes):
        put("全部语言导出成功\n")

    # 导出成功后执行上传
    upload_svn_dirs = step.get("upload_svn_dir", [])
    if isinstance(upload_svn_dirs, str):
        upload_svn_dirs = [d.strip() for d in upload_svn_dirs.split(",") if d.strip()]
    if ok_count > 0 and upload_svn_dirs:
        put(f"\n导出完成，执行上传\n")
        _exec_upload_svn({"dirs": upload_svn_dirs}, put, task_id)

    return ok_count == len(codes)


def _exec_merge_translation(step, put, task_id=None):  # noqa: C901
    excel_file = step.get("input_file", "").strip()
    original_file = step.get("original_file", "").strip()
    sheet_name = step.get("sheet_name", "").strip()

    if not excel_file or not os.path.exists(excel_file):
        put("翻译文件无效: " + str(excel_file) + "\n")
        return False
    if not original_file or not os.path.exists(original_file):
        put("原文件无效: " + str(original_file) + "\n")
        return False

    put("翻译文件: " + excel_file + "\n")
    put("原文件: " + original_file + "\n")

    # 合并前更新原文件对应的 gameData 目录
    _find_and_update_gamedata(original_file, put, task_id)

    # 合并前锁定目标文件
    if not _exec_lock_svn({"target_path": original_file, "lock_msg": "合并翻译前锁定", "update_dirs": []}, put, task_id):
        return False

    import openpyxl

    try:
        trans_wb = openpyxl.load_workbook(excel_file, data_only=True)
        orig_wb = openpyxl.load_workbook(original_file)

        id_keys = ["id", "i_d", "编号", "key"]

        _cfg = load_config()
        _lang_id_map = _cfg.get("tr_lang_id_map", {})
        _chinese_ids = set()
        for _ln, _ids in _lang_id_map.items():
            if "中文" in _ln or _ln.strip().lower() in ("chinese", "简体中文", "中文"):
                for _id in _ids:
                    _chinese_ids.add(_id.strip().lower())
        if not _chinese_ids:
            _chinese_ids = {"zh", "zh_cn", "zh-cn", "zh cn", "chinese", "简体中文", "中文", "简中", "cn"}

        if sheet_name:
            if sheet_name not in trans_wb.sheetnames:
                put("翻译文件中无 Sheet: " + sheet_name + "\n")
                trans_wb.close()
                orig_wb.close()
                return False
            if sheet_name not in orig_wb.sheetnames:
                put("原文件中无 Sheet: " + sheet_name + "\n")
                trans_wb.close()
                orig_wb.close()
                return False
            process_sheets = [sheet_name]
        else:
            process_sheets = [sn for sn in trans_wb.sheetnames if sn in orig_wb.sheetnames]

        global_mode = False
        if not process_sheets:
            put("两文件无共有 Sheet，启用跨 Sheet ID 匹配模式\n")
            global_mode = True

            orig_headers_by_sheet = {}
            orig_global_id_map = {}

            def _find_header_row(ws):
                for r in range(1, min(ws.max_row, 6) + 1):
                    count = 0
                    for c in range(1, min(ws.max_column, 20) + 1):
                        v = ws.cell(row=r, column=c).value
                        if v is not None and isinstance(v, str) and v.strip():
                            count += 1
                    if count >= 3:
                        return r
                return 1

            def _clean_header(name):
                return name.strip().lower().strip(":").strip()

            for orig_sn in orig_wb.sheetnames:
                orig_ws = orig_wb[orig_sn]
                hdr_row = _find_header_row(orig_ws)
                oh = {}
                for col in range(1, orig_ws.max_column + 1):
                    h = orig_ws.cell(row=hdr_row, column=col).value
                    if h is not None:
                        cleaned = _clean_header(str(h))
                        if cleaned:
                            oh[cleaned] = col
                orig_headers_by_sheet[orig_sn] = oh

                orig_id_col_gs = None
                for k in id_keys:
                    if k in oh:
                        orig_id_col_gs = oh[k]
                        break
                if orig_id_col_gs is None:
                    continue

                for row in range(hdr_row + 1, orig_ws.max_row + 1):
                    val = orig_ws.cell(row=row, column=orig_id_col_gs).value
                    if val is not None:
                        key = str(val).strip()
                        if key and key not in orig_global_id_map:
                            orig_global_id_map[key] = (orig_sn, row)

            process_sheets = trans_wb.sheetnames
            put("  扫描原文件 " + str(len(orig_headers_by_sheet)) + " 个 Sheet, " + str(len(orig_global_id_map)) + " 个 ID\n")

        sheet_ops = []

        for sn in process_sheets:
            trans_ws = trans_wb[sn]

            trans_headers = {}
            for col in range(1, trans_ws.max_column + 1):
                h = trans_ws.cell(row=1, column=col).value
                if h is not None:
                    cleaned = str(h).strip().lower().strip(":").strip()
                    if cleaned:
                        trans_headers[cleaned] = col

            trans_id_col = None
            for k in id_keys:
                if k in trans_headers:
                    trans_id_col = trans_headers[k]
                    break
            if trans_id_col is None and trans_headers:
                first_key = next(iter(trans_headers))
                trans_id_col = trans_headers[first_key]

            if global_mode:
                header_col_map = {}
                for h_name, t_col in trans_headers.items():
                    if t_col == trans_id_col:
                        continue
                    if h_name in _chinese_ids:
                        continue
                    for o_sn, oh in orig_headers_by_sheet.items():
                        if h_name in oh:
                            header_col_map.setdefault(o_sn, {})[t_col] = oh[h_name]
                if not header_col_map:
                    put("  Sheet " + sn + ": 无匹配的翻译列\n")
                    continue

                updates_by_orig_sheet = {}
                matched_rows = 0
                for row in range(2, trans_ws.max_row + 1):
                    id_val = trans_ws.cell(row=row, column=trans_id_col).value
                    if id_val is None:
                        continue
                    id_key = str(id_val).strip()
                    if not id_key or id_key not in orig_global_id_map:
                        continue
                    matched_rows += 1
                    orig_sn, orig_row = orig_global_id_map[id_key]
                    if orig_sn not in header_col_map:
                        continue
                    col_map = header_col_map[orig_sn]
                    orig_ws_local = orig_wb[orig_sn]
                    for t_col, o_col in col_map.items():
                        val = trans_ws.cell(row=row, column=t_col).value
                        if val is not None:
                            val_str = str(val)
                            orig_current = orig_ws_local.cell(row=orig_row, column=o_col).value
                            orig_current_str = str(orig_current or "")
                            if val_str.strip() != orig_current_str.strip():
                                updates_by_orig_sheet.setdefault(orig_sn, []).append((orig_row, o_col, val))

                for o_sn, upds in updates_by_orig_sheet.items():
                    sheet_ops.append({"sheet": o_sn, "updates": upds, "inserts": []})
                total_upd = sum(len(v) for v in updates_by_orig_sheet.values())
                if total_upd > 0:
                    put("  Sheet " + sn + ": 匹配 " + str(matched_rows) + " 行, " + str(total_upd) + " 个单元格待更新（跨 " + str(len(updates_by_orig_sheet)) + " 个原Sheet）\n")
                else:
                    put("  Sheet " + sn + ": 匹配 " + str(matched_rows) + " 行, 无变更\n")
            else:
                orig_ws = orig_wb[sn]

                orig_headers = {}
                for col in range(1, orig_ws.max_column + 1):
                    h = orig_ws.cell(row=1, column=col).value
                    if h is not None:
                        cleaned = str(h).strip().lower().strip(":").strip()
                        if cleaned:
                            orig_headers[cleaned] = col

                orig_id_col = None
                for k in id_keys:
                    if k in trans_headers and k in orig_headers:
                        orig_id_col = orig_headers[k]
                        break
                if orig_id_col is None:
                    common = [k for k in trans_headers if k in orig_headers]
                    if common:
                        orig_id_col = orig_headers[common[0]]
                    else:
                        put("  Sheet " + sn + ": 无共有表头列，跳过\n")
                        continue

                orig_id_map = {}
                for row in range(2, orig_ws.max_row + 1):
                    val = orig_ws.cell(row=row, column=orig_id_col).value
                    if val is not None:
                        key = str(val).strip()
                        if key:
                            orig_id_map[key] = row

                header_col_map = {}
                for h_name, t_col in trans_headers.items():
                    if t_col == trans_id_col:
                        continue
                    if h_name in _chinese_ids:
                        continue
                    if h_name in orig_headers:
                        header_col_map[t_col] = orig_headers[h_name]

                if not header_col_map:
                    put("  Sheet " + sn + ": 无匹配的翻译列\n")
                    continue

                updates = []
                matched_rows = 0
                for row in range(2, trans_ws.max_row + 1):
                    id_val = trans_ws.cell(row=row, column=trans_id_col).value
                    if id_val is None:
                        continue
                    id_key = str(id_val).strip()
                    if not id_key or id_key not in orig_id_map:
                        continue
                    matched_rows += 1
                    orig_row = orig_id_map[id_key]
                    for t_col, o_col in header_col_map.items():
                        val = trans_ws.cell(row=row, column=t_col).value
                        if val is not None:
                            val_str = str(val)
                            orig_current = orig_ws.cell(row=orig_row, column=o_col).value
                            orig_current_str = str(orig_current or "")
                            if val_str.strip() != orig_current_str.strip():
                                updates.append((orig_row, o_col, val))

                if updates:
                    sheet_ops.append({"sheet": sn, "updates": updates, "inserts": []})
                    put("  Sheet " + sn + ": 匹配 " + str(matched_rows) + " 行, " + str(len(updates)) + " 个单元格待更新\n")
                else:
                    put("  Sheet " + sn + ": 匹配 " + str(matched_rows) + " 行, 无变更\n")

        trans_wb.close()
        orig_wb.close()

        if not sheet_ops:
            put("没有需要更新的内容\n")
            return True

        if _check_office_lock(original_file):
            put("原文件被 WPS/Excel 锁定，无法保存\n")
            return False

        put("Excel 后台写入中...\n")
        ok, err_msg = apply_via_excel(original_file, sheet_ops)
        if ok:
            total_updates = sum(len(ops["updates"]) for ops in sheet_ops)
            put("已保存: " + os.path.basename(original_file) + "\n")
            put("合并翻译完成: 更新 " + str(total_updates) + " 个单元格\n")
            return True
        else:
            put("Excel 写入失败: " + err_msg + "\n")
            return False

    except Exception as e:
        put("处理失败: " + str(e) + "\n")
        import traceback
        put(traceback.format_exc() + "\n")
        return False


def _protect_tw_text(text):
    placeholders = {}

    def hold(match):
        key = "{P" + str(len(placeholders)) + "}"
        placeholders[key] = match.group(0)
        return key

    protected = re.sub(r"(<[^>]*>|\[[^\]\r\n]*\]|\{\d+\}|%[sdif])", hold, text)
    out = []
    i = 0
    n = len(protected)
    while i < n:
        ch = protected[i]
        if ch == "\r":
            out.append("{R}")
            i += 1
        elif ch == "\n":
            out.append("{N}")
            i += 1
        elif ch == "\t":
            out.append("{T}")
            i += 1
        elif ch == " ":
            j = i
            while j < n and protected[j] == " ":
                j += 1
            run = j - i
            if i == 0 or j == n or run > 1:
                out.append("{S}" * run)
            else:
                out.append(" ")
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out), placeholders


def _restore_tw_text(text, placeholders):
    restored = (text.replace("{R}", "\r")
                    .replace("{N}", "\n")
                    .replace("{T}", "\t")
                    .replace("{S}", " "))
    for key, val in placeholders.items():
        restored = restored.replace(key, val)
    return restored


def _ai_convert_to_tw(texts, cfg, put):
    api_url = (cfg.get("tr_api_url") or "").strip()
    api_key = (cfg.get("tr_api_key") or "").strip()
    model = (cfg.get("tr_model") or "").strip() or "gpt-4o-mini"
    if not api_url or not api_key:
        put("  ⚠ 未配置翻译 API，跳过 ::TW:: AI繁体转换\n")
        return None

    import requests
    protected_items = [_protect_tw_text(t) for t in texts]
    numbered = [str(i + 1) + "|" + item[0] for i, item in enumerate(protected_items)]
    messages = [
        {"role": "system", "content": "你是简体中文转繁体中文工具。只做简体到繁体转换，不翻译、不解释、不改变格式、标签、占位符和换行。"},
        {"role": "user", "content": "请将以下文本转换为繁体中文。严格按格式返回：编号|繁体文本。文本中的 {R}、{N}、{T}、{S}、{P数字} 是格式占位符，必须原样保留。\n\n" + "\n".join(numbered)}
    ]
    payload = {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 4096 + len(texts) * 200}
    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=300)
        if resp.status_code != 200:
            put("  ⚠ ::TW:: AI繁体转换失败: API返回 " + str(resp.status_code) + "\n")
            return None
        raw = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        put("  ⚠ ::TW:: AI繁体转换异常: " + str(e) + "\n")
        return None

    results = [None] * len(texts)
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\s*(\d+)\s*[|.:、]\s*(.*)", line)
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(texts):
            results[idx] = _restore_tw_text(m.group(2), protected_items[idx][1])
    return results


def _apply_ai_tw_conversion(wb_tgt, source_ids_by_sheet, title_rows, id_col, cfg, put):
    if not source_ids_by_sheet:
        return
    items = []
    for sn, source_ids in source_ids_by_sheet.items():
        if sn not in wb_tgt.sheetnames:
            continue
        ws = wb_tgt[sn]
        sc_col = tw_col = None
        for col in range(1, ws.max_column + 1):
            h = ws.cell(row=title_rows, column=col).value
            h_str = str(h).strip() if h is not None else ""
            if h_str == "::SC::":
                sc_col = col
            elif h_str == "::TW::":
                tw_col = col
        if not sc_col or not tw_col:
            continue
        for row in range(title_rows + 1, ws.max_row + 1):
            id_val = ws.cell(row=row, column=id_col).value
            if id_val is None or str(id_val).strip() not in source_ids:
                continue
            sc_val = ws.cell(row=row, column=sc_col).value
            if sc_val is None or not str(sc_val).strip():
                continue
            items.append((ws, row, tw_col, str(sc_val)))
    if not items:
        return

    put("  正在 AI 转换 ::TW:: 繁体: " + str(len(items)) + " 行\n")
    batch_size = int(cfg.get("tr_batch_size") or 20)
    converted = 0
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        results = _ai_convert_to_tw([item[3] for item in batch], cfg, put)
        if results is None:
            continue
        for (ws, row, tw_col, _), val in zip(batch, results):
            if val:
                ws.cell(row=row, column=tw_col).value = val
                converted += 1
    put("  ::TW:: AI繁体转换完成: " + str(converted) + "/" + str(len(items)) + " 行\n")


def _exec_merge_table(step, put, task_id=None):
    from toolbox_config import load_config
    cfg = load_config()
    input_dir = (step.get("input_dir") or "").strip()
    target_dir = (step.get("target_dir") or "").strip()
    title_rows = int(step.get("title_rows") or cfg.get("cmp_title_rows") or "1")
    id_col = int(step.get("id_col") or cfg.get("cmp_id_col") or "1")

    # ── 输入路径解析：支持文件或目录 ──
    if not input_dir or not os.path.exists(input_dir):
        put(f"输入路径无效: {input_dir}\n")
        return False

    import openpyxl

    excel_ext = (".xlsx", ".xlsm")
    if os.path.isfile(input_dir):
        src_files = [input_dir]
        input_label = os.path.dirname(input_dir)
    else:
        src_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir)
                     if f.lower().endswith(excel_ext) and os.path.isfile(os.path.join(input_dir, f))]
        src_files.sort()
        input_label = input_dir

    if not src_files:
        put(f"{'文件' if os.path.isfile(input_dir) else '目录'}下没有 Excel 文件: {input_dir}\n")
        return True

    # ── 目标路径解析：文件 → 取其所在目录 ──
    if not target_dir or not os.path.exists(target_dir):
        put(f"目标路径无效: {target_dir}\n")
        return False

    if os.path.isfile(target_dir):
        target_dir = os.path.dirname(target_dir)

    put(f"输入: {input_label} ({len(src_files)} 个 Excel)\n")
    put(f"目标目录: {target_dir}\n\n")

    # 合并前更新 gameData 目录
    _find_and_update_gamedata(target_dir, put, task_id)

    id_col_idx = id_col - 1
    merged = skipped = failed = 0

    for src_path in src_files:
        fname = os.path.basename(src_path)
        target_path = os.path.join(target_dir, fname)

        if not os.path.isfile(target_path):
            put(f"⏭ 跳过(目标无同名文件): {fname}\n")
            skipped += 1
            continue

        # 锁定目标文件，被他人锁住时跳过该文件
        put(f"正在锁定目标文件: {fname}\n")
        if not _exec_lock_svn({"target_path": target_path, "lock_msg": "合并表格前锁定", "update_dirs": []}, put, task_id):
            failed += 1
            continue

        put(f"{'='*50}\n")
        put(f"处理: {fname}\n")

        # 读取输入文件
        try:
            wb_in = openpyxl.load_workbook(src_path, read_only=True, data_only=True)
        except Exception as e:
            put(f"✗ 读取输入失败: {e}\n")
            failed += 1
            continue

        # 打开目标文件（可写模式，保留 xlsm 结构）
        try:
            wb_tgt = openpyxl.load_workbook(target_path)
        except Exception as e:
            put(f"✗ 打开目标文件失败: {e}\n")
            failed += 1
            continue

        # 从目标文件获取 ID 列头
        tgt_id_header = None
        for sn in wb_tgt.sheetnames:
            if wb_tgt[sn].max_row >= title_rows:
                v = wb_tgt[sn].cell(row=title_rows, column=id_col).value
                if v:
                    tgt_id_header = str(v).strip()
                    if tgt_id_header:
                        break
        if not tgt_id_header:
            put("✗ 在目标文件中未找到 ID 列头\n")
            failed += 1
            continue

        # ── Phase 0: 构建全局 ID 索引 ──
        global_id_sheets = {}  # id → set(sheet_names)
        for inp_sn in wb_in.sheetnames:
            ws_in = wb_in[inp_sn]
            if ws_in.max_row < title_rows + 1:
                continue
            inp_id_col = None
            for col in range(1, ws_in.max_column + 1):
                h = ws_in.cell(row=title_rows, column=col).value
                if h and str(h).strip() == tgt_id_header:
                    inp_id_col = col
                    break
            if inp_id_col is None:
                continue
            for r in range(title_rows + 1, ws_in.max_row + 1):
                op_val = ws_in.cell(row=r, column=1).value
                if op_val is not None and str(op_val).strip() == "删除":
                    continue
                v = ws_in.cell(row=r, column=inp_id_col).value
                if v is not None:
                    sid = str(v).strip()
                    if sid and sid not in ("::ID::", "ID"):
                        global_id_sheets.setdefault(sid, set()).add(inp_sn)

        dup_ids = {sid for sid, sheets in global_id_sheets.items() if len(sheets) > 1}
        if dup_ids:
            put(f"  ℹ 发现 {len(dup_ids)} 个跨 sheet 重复 ID\n")

        input_count = 0
        processed_dup_logged = False
        source_ids_by_sheet = {}

        for inp_sn in wb_in.sheetnames:
            ws_in = wb_in[inp_sn]
            if ws_in.max_row < title_rows + 1:
                continue

            # 匹配目标 sheet
            tgt_sn = inp_sn if inp_sn in wb_tgt.sheetnames else None
            if tgt_sn is None:
                sheet_col = None
                for col in range(1, ws_in.max_column + 1):
                    h = ws_in.cell(row=title_rows, column=col).value
                    if h and str(h).strip().lower() == "sheet":
                        sheet_col = col
                        break
                if sheet_col is None:
                    continue
                sheet_rows = {}
                for r in range(title_rows + 1, ws_in.max_row + 1):
                    op_val = ws_in.cell(row=r, column=1).value
                    if op_val is not None and str(op_val).strip() == "删除":
                        continue
                    v = ws_in.cell(row=r, column=sheet_col).value
                    if v is not None:
                        sn = str(v).strip()
                        if sn:
                            sheet_rows.setdefault(sn, []).append(r)
                for tgt_sn, rows in sheet_rows.items():
                    if tgt_sn not in wb_tgt.sheetnames:
                        continue
                    ws_tgt = wb_tgt[tgt_sn]
                    added, updated, source_ids = _merge_sheet_rows(
                        ws_in, ws_tgt, rows, title_rows, id_col, dup_ids, put)
                    input_count += added
                    if source_ids:
                        source_ids_by_sheet.setdefault(tgt_sn, set()).update(source_ids)
                continue

            ws_tgt = wb_tgt[tgt_sn]
            all_rows = []
            for r in range(title_rows + 1, ws_in.max_row + 1):
                op_val = ws_in.cell(row=r, column=1).value
                if op_val is not None and str(op_val).strip() == "删除":
                    continue
                all_rows.append(r)
            added, updated, source_ids = _merge_sheet_rows(
                ws_in, ws_tgt, all_rows, title_rows, id_col, dup_ids, put)
            input_count += added
            if source_ids:
                source_ids_by_sheet.setdefault(tgt_sn, set()).update(source_ids)

        _apply_ai_tw_conversion(wb_tgt, source_ids_by_sheet, title_rows, id_col, cfg, put)
        wb_in.close()
        wb_tgt.save(target_path)
        # 用 Excel/WPS COM 重写文件，修复 openpyxl 兼容性问题
        for app in ["Excel.Application", "Ket.Application"]:
            try:
                import win32com.client as win32
                xl = win32.DispatchEx(app)
                xl.Visible = False
                xl.DisplayAlerts = False
                wb = xl.Workbooks.Open(target_path)
                wb.Save()
                wb.Close()
                xl.Quit()
                break
            except Exception:
                continue
        wb_tgt.close()
        merged += 1
        put(f"✓ 合并完成 (输入 {input_count} 行)\n")

        # ── Phase 2: 报告重复 ID ──
        if dup_ids:
            dup_list = sorted(dup_ids)
            put(f"  ⚠ 以下 {len(dup_list)} 个 ID 存在于多个 sheet:\n")
            for did in dup_list:
                sheets = sorted(global_id_sheets[did])
                put(f"    {did}: {', '.join(sheets)}\n")

    put(f"\n── 合并完成: {merged} 成功, {skipped} 跳过(无同名), {failed} 失败 ──\n")
    return failed == 0


def _merge_sheet_rows(ws_in, ws_tgt, inp_rows, title_rows, id_col, dup_ids, put):
    """按 ID 合并 sheet：更新现有行、追加新增行。返回 (added, updated, source_ids)
    
    对齐 Tkinter 旧版逻辑：
    - ID 列按列头文字匹配
    - 数据列按 (列头, 出现次数) 元匹配（支持重复列头）
    - 连续数据区识别，END 标记处理：
      有 END 时旧 END 行变 "0"，新行插在 END 后，最后一行变 "END"
    - dup_ids: 跨 sheet 重复的 ID 集合，用于日志标注 """
    id_col_num = id_col
    if id_col_num > ws_tgt.max_column:
        return 0, 0, set()

    tgt_id_header = str(ws_tgt.cell(row=title_rows, column=id_col_num).value or "").strip()
    if not tgt_id_header:
        return 0, 0, set()

    inp_id_col = None
    for col in range(1, ws_in.max_column + 1):
        h = ws_in.cell(row=title_rows, column=col).value
        if h and str(h).strip() == tgt_id_header:
            inp_id_col = col
            break
    if inp_id_col is None:
        return 0, 0, set()

    # ── 查找连续数据区 ──
    last_continuous_id_row = title_rows
    for r in range(title_rows + 1, ws_tgt.max_row + 1):
        val = ws_tgt.cell(row=r, column=id_col_num).value
        if val is not None and str(val).strip():
            last_continuous_id_row = r
        else:
            break

    # ── 查找 END 标记 ──
    has_end = False
    end_row_at = None
    if last_continuous_id_row >= title_rows + 1:
        for r in range(last_continuous_id_row, ws_tgt.max_row + 1):
            val = ws_tgt.cell(row=r, column=1).value
            if val is not None and str(val).strip().lower() == "end":
                has_end = True
                end_row_at = r
                break

    # ── 构建目标 ID → 行号 映射（连续数据区内） ──
    tgt_id_map = {}
    for r in range(title_rows + 1, last_continuous_id_row + 1):
        val = ws_tgt.cell(row=r, column=id_col_num).value
        if val is not None:
            key = str(val).strip()
            if key:
                tgt_id_map[key] = r

    updated = 0
    source_ids = set()
    new_rows_data = []  # 待插入行的 (inp_id, col_data) 列表

    for inp_r in inp_rows:
        inp_id_val = ws_in.cell(row=inp_r, column=inp_id_col).value
        if inp_id_val is None:
            continue
        inp_id = str(inp_id_val).strip()
        if not inp_id or inp_id in ("::ID::", "ID"):
            continue
        source_ids.add(inp_id)

        # 读取输入行数据，按 (列头, 出现次数) 为 key（从列 2 开始，列 1 为 ID）
        inp_hdr_count = {}
        row_data = {}
        for col in range(2, ws_in.max_column + 1):
            h = ws_in.cell(row=title_rows, column=col).value
            if h is not None:
                h_str = str(h).strip()
                occ = inp_hdr_count.get(h_str, 0)
                inp_hdr_count[h_str] = occ + 1
                val = ws_in.cell(row=inp_r, column=col).value
                row_data[(h_str, occ)] = val

        if inp_id in tgt_id_map:
            # ── 更新：按目标列头匹配写入 ──
            tgt_r = tgt_id_map[inp_id]
            tgt_hdr_count = {}
            for col in range(1, ws_tgt.max_column + 1):
                h = ws_tgt.cell(row=title_rows, column=col).value
                if h is not None:
                    h_str = str(h).strip()
                    occ = tgt_hdr_count.get(h_str, 0)
                    tgt_hdr_count[h_str] = occ + 1
                    if h_str != tgt_id_header and col != 1:
                        key = (h_str, occ)
                        if key in row_data:
                            ws_tgt.cell(row=tgt_r, column=col).value = row_data[key]
            updated += 1
        else:
            # ── 插入：按目标列头匹配收集数据（跳过列 1） ──
            tgt_hdr_count = {}
            col_data = {}
            for col in range(1, ws_tgt.max_column + 1):
                h = ws_tgt.cell(row=title_rows, column=col).value
                if h is not None:
                    h_str = str(h).strip()
                    occ = tgt_hdr_count.get(h_str, 0)
                    tgt_hdr_count[h_str] = occ + 1
                    if col == 1:
                        continue
                    key = (h_str, occ)
                    if key in row_data:
                        col_data[col] = row_data[key]
            new_rows_data.append((inp_id, col_data))

    # ── 批量写入插入行 ──
    added = len(new_rows_data)
    if new_rows_data:
        if has_end:
            # END → "0"，新行插在 END 后，最后一行变 "END"
            ws_tgt.cell(row=end_row_at, column=1).value = "0"
            for col, val in new_rows_data[0][1].items():
                ws_tgt.cell(row=end_row_at, column=col).value = val
            for i in range(1, len(new_rows_data)):
                inp_id, col_data = new_rows_data[i]
                tgt_r = end_row_at + i
                col_data[1] = "0" if i < len(new_rows_data) - 1 else "END"
                for col, val in col_data.items():
                    ws_tgt.cell(row=tgt_r, column=col).value = val
        else:
            after_row = last_continuous_id_row
            for i, (inp_id, col_data) in enumerate(new_rows_data):
                col_data[1] = inp_id
                tgt_r = after_row + 1 + i
                for col, val in col_data.items():
                    ws_tgt.cell(row=tgt_r, column=col).value = val

    if added > 0 or updated > 0:
        put(f"    {ws_in.title}: 新增 {added} 行, 更新 {updated} 行\n")
    return added, updated, source_ids


# ═══════════════════════════════════════════════════════════
# 语言ID映射 API
# ═══════════════════════════════════════════════════════════


def _import_lang_map_txt_to_json():
    """从 lang_map.txt 读取并合并为 {语言名: [ID列表]} 格式"""
    map_path = os.path.join(SCRIPT_DIR, "lang_map.txt")
    result = {}
    if not os.path.isfile(map_path):
        return result
    try:
        with open(map_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key and val:
                        if val not in result:
                            result[val] = []
                        if key not in result[val]:
                            result[val].append(key)
    except Exception:
        pass
    return result


@app.route("/api/translate/lang-id-map", methods=["GET", "POST"])
def api_translate_lang_id_map():
    if request.method == "GET":
        cfg = load_config()
        data = cfg.get("tr_lang_id_map", {})
        if not data:
            data = _import_lang_map_txt_to_json()
            if data:
                cfg["tr_lang_id_map"] = data
                save_config(cfg)
        return jsonify({"data": data})
    data = request.get_json(force=True)
    lang_id_map = data.get("lang_id_map", {})
    cfg = load_config()
    cfg["tr_lang_id_map"] = lang_id_map
    save_config(cfg)
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════
# 翻译执行 API
# ═══════════════════════════════════════════════════════════


@app.route("/api/translate/run", methods=["POST"])
def api_translate_run():  # noqa: C901
    data = request.get_json(force=True)
    src_path = data.get("src_path", "").strip()
    ref_path = data.get("ref_path", "").strip()
    api_url = data.get("api_url", "").strip()
    api_key = data.get("api_key", "").strip()
    model = data.get("model", "gpt-4o-mini").strip()
    src_lang = data.get("src_lang", "").strip()
    tgt_langs = data.get("tgt_langs", [])
    out_dir = data.get("out_dir", DEFAULT_OUTPUT_DIR).strip()
    prompt_template = data.get("prompt", "").strip()
    batch_size = int(data.get("batch_size", 20))

    if not src_path or not os.path.isfile(src_path):
        return jsonify({"error": "请选择有效的翻译表格"}), 400
    if not api_key:
        return jsonify({"error": "请输入 API Key"}), 400
    if not tgt_langs:
        return jsonify({"error": "请选择目标语言"}), 400

    os.makedirs(out_dir, exist_ok=True)

    # 保存配置
    cfg = load_config()
    for k, v in [("tr_src_history", src_path), ("tr_ref_history", ref_path),
                 ("tr_api_url", api_url), ("tr_model", model),
                 ("tr_src_lang", src_lang), ("tr_out_dir", out_dir),
                 ("tr_prompt", prompt_template), ("tr_batch_size", batch_size)]:
        if k.endswith("_history"):
            hist = cfg.get(k, [])
            if v and v not in hist:
                hist.insert(0, v)
                cfg[k] = hist[:20]
        elif v or isinstance(v, int):
            cfg[k] = v
    save_config(cfg)

    task_id = _get_next_task_id()
    q = queue.Queue()
    _log_queues[task_id] = q

    def _run():
        import openpyxl
        import requests
        import time as _time
        import re as _re

        q.put(f"{'='*50}\n")
        q.put("开始翻译\n")
        q.put(f"源文件: {src_path}\n")
        q.put(f"源语言: {src_lang}\n")
        q.put(f"目标语言: {', '.join(tgt_langs)}\n")
        q.put(f"模型: {model}\n\n")

        base_name = os.path.splitext(os.path.basename(src_path))[0]
        if len(tgt_langs) == 1:
            safe_tgt = tgt_langs[0].strip(":").replace(" ", "_")
            out_name = f"翻译_{base_name}_{safe_tgt}.xlsx"
        else:
            out_name = f"翻译_{base_name}_多语言.xlsx"
        out_path = os.path.join(out_dir, out_name)

        def _clean(name):
            return name.strip(":")
        clean_src = _clean(src_lang)
        clean_tgts = [_clean(t) for t in tgt_langs]
        lang_display = "、".join(clean_tgts)

        # 加载语言ID映射，构建反转表 {关键词小写: 语言名}
        _lang_id_map = dict(load_config().get("tr_lang_id_map", {}))
        _header_to_lang_map = {}
        _any_id_to_lang = {}
        for lang_name, ids in _lang_id_map.items():
            _any_id_to_lang[lang_name.lower()] = lang_name
            for id_str in ids:
                key = id_str.strip().lower()
                _header_to_lang_map[key] = lang_name
                _any_id_to_lang[key] = lang_name

        def _header_to_lang(header_lower):
            return _header_to_lang_map.get(header_lower)

        def _resolve_lang(val):
            """将语言代码/ID/名称统一解析为语言名，用于匹配"""
            v = val.strip().lower()
            return _any_id_to_lang.get(v, val)

        def _match_col(val, headers_list):
            """检查 val 是否匹配某个表头，返回 (列索引从1开始, 匹配到的表头)
            匹配优先级:
            1) 表头被语言映射识别到的语言名与 val 的语言名相同
            2) 表头文本与 val 大小写不敏感匹配
            """
            val_lower = val.strip().lower()
            val_lang = _resolve_lang(val)
            for i, h in enumerate(headers_list, 1):
                hl = h.lower()
                header_lang = _header_to_lang(hl)
                if header_lang and val_lang and header_lang == val_lang:
                    return i, h
                if hl == val_lower:
                    return i, h
            return None, None

        prompt = (prompt_template or "请将以下文本从{src_lang}翻译为{tgt_lang}，保持格式不变")
        system_prompt = prompt.replace("{src_lang}", clean_src).replace("{tgt_lang}", lang_display)

        def _protect_translate_text(text):
            placeholders = {}

            def hold(match):
                key = "{P" + str(len(placeholders)) + "}"
                placeholders[key] = match.group(0)
                return key

            protected = _re.sub(r"(<[^>]*>|\[[^\]\r\n]*\]|\{\d+\}|%[sdif])", hold, text)
            out = []
            i = 0
            n = len(protected)
            while i < n:
                ch = protected[i]
                if ch == "\r":
                    out.append("{R}")
                    i += 1
                elif ch == "\n":
                    out.append("{N}")
                    i += 1
                elif ch == "\t":
                    out.append("{T}")
                    i += 1
                elif ch == " ":
                    j = i
                    while j < n and protected[j] == " ":
                        j += 1
                    run = j - i
                    if i == 0 or j == n or run > 1:
                        out.append("{S}" * run)
                    else:
                        out.append(" ")
                    i = j
                else:
                    out.append(ch)
                    i += 1
            return "".join(out), placeholders

        def _restore_translate_text(text, placeholders=None):
            restored = (text.replace("{R}", "\r")
                            .replace("{N}", "\n")
                            .replace("{T}", "\t")
                            .replace("{S}", " "))
            if placeholders:
                for key, val in placeholders.items():
                    restored = restored.replace(key, val)
            return restored

        def _number_format_rule(lang):
            rules = {
                "英语": (",", "."), "英文": (",", "."),
                "俄语": ("", ","), "俄文": ("", ","),
                "法语": (" ", ","), "法文": (" ", ","),
                "德语": (".", ","), "德文": (".", ","),
                "葡萄牙语": (".", ","), "葡萄牙文": (".", ","),
                "西班牙语": (",", "."), "西班牙文": (",", "."),
                "土耳其语": (".", ","), "土耳其文": (".", ","),
            }
            return rules.get(_clean(lang))

        def _format_number_token(token, thousands_sep, decimal_sep):
            compact = token.replace(" ", "")
            dot_pos = compact.rfind(".")
            comma_pos = compact.rfind(",")
            sep_pos = max(dot_pos, comma_pos)
            frac = None
            head = compact
            if sep_pos > 0:
                tail = compact[sep_pos + 1:]
                before = compact[:sep_pos]
                if tail.isdigit() and 1 <= len(tail) <= 2 and any(ch.isdigit() for ch in before):
                    head = before
                    frac = tail
            digits = _re.sub(r"[., ]", "", head)
            if not digits.isdigit():
                return token
            if len(digits) < 4 and frac is None:
                return token
            if thousands_sep:
                groups = []
                while len(digits) > 3:
                    groups.insert(0, digits[-3:])
                    digits = digits[:-3]
                groups.insert(0, digits)
                out = thousands_sep.join(groups)
            else:
                out = digits
            if frac is not None:
                out += decimal_sep + frac
            return out

        def _format_numbers_for_lang(text, lang):
            rule = _number_format_rule(lang)
            if not rule:
                return text
            thousands_sep, decimal_sep = rule
            protected_re = _re.compile(r"(<[^>]*>|\[[^\]]*\]|\{\d+\}|%[sdif])")
            number_re = _re.compile(r"(?<![\w])\d[\d., ]*\d|(?<![\w])\d(?![\w])")
            parts = protected_re.split(text)
            for i in range(0, len(parts), 2):
                parts[i] = number_re.sub(
                    lambda m: _format_number_token(m.group(0), thousands_sep, decimal_sep),
                    parts[i]
                )
            return "".join(parts)

        def _load_ref(tgt_lang_name):
            refs = {}
            if not ref_path or not os.path.isfile(ref_path):
                return refs
            ext = os.path.splitext(ref_path)[1].lower()
            try:
                if ext in (".xlsx", ".xlsm"):
                    rwb = openpyxl.load_workbook(ref_path, read_only=True, data_only=True)
                    rws = rwb.active
                    rheaders = [str(c.value).strip() if c.value is not None else "" for c in rws[1]]
                    src_idx, _ = _match_col(src_lang, rheaders)
                    tgt_idx, _ = _match_col(tgt_lang_name, rheaders)
                    if src_idx is not None and tgt_idx is not None:
                        for row in rws.iter_rows(min_row=2, values_only=True):
                            if row[src_idx] and row[tgt_idx]:
                                refs[str(row[src_idx]).strip()] = str(row[tgt_idx]).strip()
                    rwb.close()
                    q.put(f"参考 ({tgt_lang_name}): {len(refs)} 条\n")
                else:
                    with open(ref_path, "r", encoding="utf-8") as f:
                        refs["__raw_text__"] = f.read()
            except Exception as e:
                q.put(f"读取参考文件失败: {e}\n")
            return refs

        def _call_api(texts, tgt_names, refs_by_target, retries=5):
            user_parts = []
            has_raw = any(r.get("__raw_text__") for r in refs_by_target.values() if r)
            if has_raw:
                for tgt in tgt_names:
                    r = refs_by_target.get(tgt, {})
                    if r.get("__raw_text__"):
                        user_parts.append(f"参考内容 ({_clean(tgt)}):\n{r['__raw_text__']}")
            else:
                ref_parts = []
                for tgt in tgt_names:
                    r = refs_by_target.get(tgt, {})
                    if r:
                        sample = list(r.items())[:30]
                        ref_parts.append(f"【{_clean(tgt)}】参考:\n" + "\n".join(f"{k} -> {v}" for k, v in sample))
                if ref_parts:
                    user_parts.append("\n".join(ref_parts))

            protected_items = [_protect_translate_text(t) for t in texts]
            numbered = [f"{i+1}|{item[0]}" for i, item in enumerate(protected_items)]
            placeholder_maps = [item[1] for item in protected_items]
            user_parts.append(
                f"请将以下文本从 {clean_src} 一次性翻译为 {lang_display}。"
                f"\n严格按照编号和分隔符格式返回，每行一条："
                f"\n编号|翻译1|翻译2|翻译3..."
                f"\n不要包含任何额外说明、解释或空行。"
                f"\n文本中的 {{R}}、{{N}}、{{T}}、{{S}}、{{P数字}} 是格式占位符，必须原样保留。"
                f"\n\n待翻译文本：\n" + "\n".join(numbered)
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "\n\n".join(user_parts)}
            ]
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4096 + len(texts) * len(tgt_names) * 200
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            for attempt in range(retries + 1):
                try:
                    resp = requests.post(api_url, headers=headers, json=payload, timeout=300)
                    if resp.status_code == 200:
                        data = resp.json()
                        usage = data.get("usage", {})
                        hit = usage.get("prompt_cache_hit_tokens", 0)
                        total_p = usage.get("prompt_tokens", 0)
                        if total_p > 0:
                            rate = hit / total_p * 100
                            q.put(f"  缓存命中 {hit}/{total_p} tokens ({rate:.1f}%)\n")
                        raw = data["choices"][0]["message"]["content"].strip()
                        results = [None] * len(texts)
                        for line in raw.split("\n"):
                            line = line.strip()
                            if not line:
                                continue
                            m = _re.match(r"^\s*(\d+)\s*[|.:、]\s*(.*)", line)
                            if m:
                                idx = int(m.group(1)) - 1
                                if 0 <= idx < len(texts):
                                    parts = m.group(2).split("|")
                                    row_result = {}
                                    for ti, tgt in enumerate(tgt_names):
                                        if ti < len(parts) and parts[ti]:
                                            restored = _restore_translate_text(parts[ti], placeholder_maps[idx])
                                            row_result[tgt] = _format_numbers_for_lang(restored, tgt)
                                    results[idx] = row_result
                        return results
                    elif resp.status_code == 429:
                        wait = 5 * (3 ** attempt)
                        q.put(f"  限流(429)，等待 {wait}s 重试 ({attempt+1}/{retries+1})\n")
                        _time.sleep(wait)
                        continue
                    else:
                        q.put(f"API 返回 {resp.status_code}: {resp.text[:200]}\n")
                        if attempt < retries:
                            _time.sleep(3)
                            continue
                        return None
                except Exception as e:
                    q.put(f"API 调用异常: {e}\n")
                    if attempt < retries:
                        _time.sleep(3)
                        continue
                    return None
            return None

        try:
            wb = openpyxl.load_workbook(src_path)
            ws = wb.active

            headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]

            src_col, src_match = _match_col(src_lang, headers)
            if src_col is None:
                q.put(f"未找到源语言列 '{src_lang}'\n")
                wb.close()
                _notify_task_done("翻译")
                q.put(None)
                return

            tgt_col_map = {}
            for tl in tgt_langs:
                col, _ = _match_col(tl, headers)
                if col is not None:
                    tgt_col_map[tl] = col
                else:
                    q.put(f"未找到目标语言列 '{tl}'，跳过\n")

            if not tgt_col_map:
                q.put("未找到任何有效的目标语言列\n")
                wb.close()
                _notify_task_done("翻译")
                q.put(None)
                return

            tgt_names = list(tgt_col_map.keys())
            cols_str = ", ".join(f"{k}({v})" for k, v in tgt_col_map.items())
            q.put(f"源列: {src_col} | 目标列: {cols_str}\n")

            q.put("加载参考文件...\n")
            all_refs = {}
            has_raw = False
            for tgt in tgt_names:
                all_refs[tgt] = _load_ref(tgt)
                if all_refs[tgt].get("__raw_text__"):
                    has_raw = True

            batch_items = []
            ref_matched = 0
            # 一次性读入内存，避免逐行创建 cell 对象
            rows_data = [list(row) for row in ws.iter_rows(min_row=2, values_only=True)]
            for ri, vals in enumerate(rows_data, 2):
                src_val = vals[src_col - 1]
                if src_val is None or not str(src_val).strip():
                    continue
                src_text = str(src_val)
                src_key = src_text.strip()

                missing_targets = set()
                for tgt_name, tgt_col in tgt_col_map.items():
                    tgt_val = vals[tgt_col - 1]
                    if tgt_val and str(tgt_val).strip():
                        continue
                    if not has_raw:
                        ref_val = all_refs.get(tgt_name, {}).get(src_key)
                        if ref_val:
                            ws.cell(row=ri, column=tgt_col, value=ref_val)
                            ref_matched += 1
                            continue
                    missing_targets.add(tgt_name)

                if missing_targets:
                    batch_items.append((ri, src_text, missing_targets))

            q.put(f"参考匹配直接填入: {ref_matched} 条\n")
            q.put(f"需要 API 翻译: {len(batch_items)} 条 -> {len(tgt_names)} 个语言\n")

            if not batch_items:
                q.put("无需 API 翻译，全部已处理\n")
                wb.save(out_path)
                wb.close()
                q.put(f"已保存: {out_path}\n")
                _notify_task_done("翻译")
                q.put(None)
                return

            overall_fail = 0
            total_batches = (len(batch_items) + batch_size - 1) // batch_size
            for batch_start in range(0, len(batch_items), batch_size):
                batch = batch_items[batch_start:batch_start + batch_size]
                texts = [item[1] for item in batch]
                rows = [item[0] for item in batch]
                missing_sets = [item[2] for item in batch]

                batch_num = batch_start // batch_size + 1
                q.put(f"批次 {batch_num}/{total_batches} ({len(texts)} 条 x {len(tgt_names)} 语言)\n")

                results = _call_api(texts, tgt_names, all_refs)
                if results is None:
                    q.put(f"  批次 {batch_num} 全部失败\n")
                    for row_num, missing in zip(rows, missing_sets):
                        for tgt_name in missing:
                            ws.cell(row=row_num, column=tgt_col_map[tgt_name], value="【翻译失败】")
                    overall_fail += sum(len(m) for m in missing_sets)
                    continue

                batch_ok = batch_fail = 0
                for row_num, row_result, missing in zip(rows, results, missing_sets):
                    if row_result is None:
                        for tgt_name in missing:
                            ws.cell(row=row_num, column=tgt_col_map[tgt_name], value="【翻译失败】")
                        batch_fail += len(missing)
                        continue
                    for tgt_name in missing:
                        trans = row_result.get(tgt_name)
                        if trans:
                            ws.cell(row=row_num, column=tgt_col_map[tgt_name], value=trans)
                            batch_ok += 1
                        else:
                            ws.cell(row=row_num, column=tgt_col_map[tgt_name], value="【翻译失败】")
                            batch_fail += 1

                overall_fail += batch_fail
                q.put(f"  批次 {batch_num} 完成（成功 {batch_ok}/{batch_ok + batch_fail}）\n")

            wb.save(out_path)
            wb.close()
            q.put(f"{'='*50}\n")
            q.put(f"[输出路径] {out_dir}\n")
            q.put(f"翻译完成! 输出文件: {out_path}\n")
        except PermissionError:
            try:
                wb.close()
            except Exception:
                pass
            q.put("翻译过程出错: 输出文件被占用，请关闭 Excel 中已打开的文件后重试\n")
        except Exception as e:
            try:
                wb.close()
            except Exception:
                pass
            import traceback
            q.put(f"翻译过程出错: {e}\n")
            q.put(traceback.format_exc() + "\n")
        _notify_task_done("翻译")
        q.put(None)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/open/folder", methods=["POST"])
def api_open_folder():
    data = request.get_json(force=True)
    path = data.get("path", "").strip()
    if not path:
        return jsonify({"error": "路径为空"}), 400
    path = os.path.normpath(path)
    if os.path.isfile(path):
        subprocess.Popen(f'explorer /select,"{path}"', shell=True)
        return jsonify({"ok": True, "path": path})
    if os.path.isdir(path):
        subprocess.Popen(f'explorer "{path}"', shell=True)
        return jsonify({"ok": True, "path": path})
    return jsonify({"error": f"路径不是目录: {path}"}), 400


@app.route("/api/svn/detect", methods=["POST"])
def api_svn_detect():
    data = request.get_json(force=True)
    path = os.path.normpath(data.get("path", "").strip())
    if not path:
        return jsonify({"ok": False, "error": "路径为空"}), 400
    try:
        svn_exe = _get_svn_path()
        check = os.path.abspath(path)
        svn_url = None
        while True:
            result = subprocess.run(
                [svn_exe, "info", "--show-item", "url", check],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=15,
                **_get_subprocess_kwargs()
            )
            url = result.stdout.strip()
            if url and result.returncode == 0:
                svn_url = url
                break
            parent = os.path.dirname(check)
            if parent == check:
                break
            check = parent
        if not svn_url and os.path.isdir(path):
            for entry in os.listdir(path):
                sub = os.path.join(path, entry)
                if os.path.isdir(os.path.join(sub, ".svn")):
                    result = subprocess.run(
                        [svn_exe, "info", "--show-item", "url", sub],
                        capture_output=True, encoding="utf-8", errors="replace",
                        timeout=15,
                        **_get_subprocess_kwargs()
                    )
                    url = result.stdout.strip()
                    if url and result.returncode == 0:
                        svn_url = url
                        break
        if svn_url:
            from urllib.parse import unquote
            svn_url = unquote(svn_url)
            return jsonify({"ok": True, "url": svn_url})
        return jsonify({"ok": False, "error": f"不是 SVN 工作副本: {path}"}), 200
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "SVN 命令不可用，请确认已安装 SVN 命令行工具"}), 200
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "SVN 命令超时"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200


def _find_svn_wc(url):
    """根据 SVN URL 查找对应的本地工作副本路径（不打开资源管理器）
    
    先查 svn_url_mappings 映射表，再走候选路径逐级匹配。
    """
    cfg = load_config()
    # 先查映射表
    clean_url = url.rstrip("/")
    mappings = cfg.get("svn_url_mappings", {})
    if clean_url in mappings:
        p = mappings[clean_url]
        if os.path.isdir(p):
            return p
    # 前缀匹配
    for map_url, local_path in mappings.items():
        if clean_url.startswith(map_url.rstrip("/") + "/"):
            rel = clean_url[len(map_url.rstrip("/")) + 1:]
            full = os.path.join(local_path, rel.replace("/", os.sep))
            if os.path.isdir(full):
                return os.path.normpath(full)
    # 候选路径逐级匹配
    candidates = set()
    for d in cfg.get("output_dir_history", []):
        if d:
            candidates.add(d)
    for u in cfg.get("svn_urls", []):
        if u and not u.startswith("http"):
            candidates.add(u)
    found = None
    for c in candidates:
        d = os.path.normpath(c)
        while True:
            try:
                r = subprocess.run(
                    ["svn", "info", "--show-item", "url", d],
                    capture_output=True, encoding="utf-8", errors="replace", timeout=5
                )
                wc_url = r.stdout.strip() if r.returncode == 0 else ""
                if wc_url and (url == wc_url or url.startswith(wc_url + "/")):
                    rel = url[len(wc_url):].lstrip("/")
                    wc = subprocess.run(
                        ["svn", "info", "--show-item", "wc-root", d],
                        capture_output=True, encoding="utf-8", errors="replace", timeout=5
                    )
                    wc_root = wc.stdout.strip()
                    found = os.path.join(wc_root, rel.replace("/", os.sep)) if rel else wc_root
                    break
            except Exception:
                pass
            parent = os.path.dirname(d)
            if parent == d or not parent:
                break
            d = parent
        if found:
            break
    return found


@app.route("/api/svn/clear-changelist", methods=["POST"])
def api_svn_clear_changelist():
    data = request.get_json(force=True)
    target_dir = data.get("target_dir", "").strip()
    if not target_dir or not os.path.isdir(target_dir):
        return jsonify({"ok": False, "error": "无效目录"}), 400
    svn_exe = _get_svn_path()
    try:
        for cl in ("语义合并", "本次修改"):
            subprocess.run(
                [svn_exe, "changelist", "--remove", "--changelist", cl, target_dir, "--depth", "infinity"],
                capture_output=True, timeout=60, **_get_subprocess_kwargs()
            )
        return jsonify({"ok": True, "message": "工具 changelist 已清理"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/svn/find-wc", methods=["POST"])
def api_svn_find_wc():
    """查找 SVN URL 对应的本地工作副本路径（不打开资源管理器）"""
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL 为空"}), 400
    found = _find_svn_wc(url)
    if found and os.path.isdir(found):
        return jsonify({"ok": True, "path": os.path.normpath(found)})
    return jsonify({"ok": False, "error": "未找到对应的本地工作副本"}), 200


@app.route("/api/svn/resolve-url", methods=["POST"])
def api_svn_resolve_url():
    """解析 SVN URL 到本地路径，找到后自动保存映射"""
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL 为空"}), 400
    cfg = load_config()
    local_path = resolve_svn_url_to_local(url, cfg=cfg)
    if local_path and os.path.isdir(local_path):
        mappings = cfg.get("svn_url_mappings", {})
        if not mappings:
            mappings = {}
        mappings[url.rstrip("/")] = os.path.normpath(local_path)
        save_config({"svn_url_mappings": mappings})
        return jsonify({"ok": True, "path": os.path.normpath(local_path)})
    return jsonify({"ok": False, "error": "未找到对应的本地工作副本路径（可尝试先填写目标路径建立映射）"}), 200


@app.route("/api/svn/save-mapping", methods=["POST"])
def api_svn_save_mapping():
    """验证并保存 URL↔本地路径映射"""
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    path = data.get("path", "").strip()
    if not url or not path:
        return jsonify({"ok": False, "error": "URL 和路径不能为空"}), 400
    if not os.path.isdir(path):
        return jsonify({"ok": False, "error": f"路径不存在: {path}"}), 200
    # 验证路径是有效的 SVN 工作副本且匹配该 URL
    try:
        svn_exe = _get_svn_path()
        r = subprocess.run(
            [svn_exe, "info", "--show-item", "url", path],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
            **_get_subprocess_kwargs()
        )
        wc_url = r.stdout.strip() if r.returncode == 0 else ""
        clean_url = url.rstrip("/")
        if not wc_url or (clean_url != wc_url and not wc_url.startswith(clean_url + "/") and not clean_url.startswith(wc_url + "/")):
            return jsonify({"ok": False, "error": f"路径 [{path}] 的 SVN URL 与输入不匹配"}), 200
        # 找到工作副本根目录
        r2 = subprocess.run(
            [svn_exe, "info", "--show-item", "wc-root", path],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
            **_get_subprocess_kwargs()
        )
        wc_root = r2.stdout.strip() if r2.returncode == 0 else path
        cfg = load_config()
        mappings = cfg.get("svn_url_mappings", {})
        if not mappings:
            mappings = {}
        new_key = clean_url
        new_val = os.path.normpath(wc_root)
        if mappings.get(new_key) != new_val:
            mappings[new_key] = new_val
            save_config({"svn_url_mappings": mappings})
        return jsonify({"ok": True, "path": new_val, "url": new_key})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "SVN 命令不可用"}), 200
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "SVN 命令超时"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200


@app.route("/api/svn/open-wc", methods=["POST"])
def api_svn_open_wc():
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL 为空"}), 400
    found = _find_svn_wc(url)
    if found and os.path.isdir(found):
        os.startfile(found)
        return jsonify({"ok": True, "path": os.path.normpath(found)})
    return jsonify({"ok": False, "error": "未找到对应的本地工作副本"}), 200


@app.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    """清除 __parse_cache__、__byte_cache__ 和 __ss_cache__ 目录"""
    total = 0
    for sub in ("__parse_cache", "__byte_cache", "__ss_cache"):
        cache_dir = os.path.join(SCRIPT_DIR, sub)
        if not os.path.exists(cache_dir):
            continue
        try:
            for fname in os.listdir(cache_dir):
                fpath = os.path.join(cache_dir, fname)
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    total += 1
        except Exception as e:
            return jsonify({"error": f"清理 {sub} 失败: {e}"}), 500
    return jsonify({"ok": True, "count": total})


# ═══════════════════════════════════════════════════════════
# SVN 精准合并 API
# ═══════════════════════════════════════════════════════════


@app.route("/api/merge/query", methods=["POST"])
def api_merge_query():
    """查询源SVN版本列表及变更文件（SSE实时日志）"""
    data = request.get_json(force=True)
    source_url = data.get("source_url", "").strip()
    start_date = data.get("start_date", "")
    end_date = data.get("end_date", "")
    author = data.get("author", "").strip() or None
    keyword = data.get("keyword", "").strip() or None
    if not source_url:
        return jsonify({"ok": False, "error": "源SVN地址不能为空"}), 400
    if not start_date or not end_date:
        return jsonify({"ok": False, "error": "请选择日期范围"}), 400
    cfg = load_config()
    svn_user = data.get("svn_user") or cfg.get("svn_user", "")
    svn_pass = data.get("svn_pass") or cfg.get("svn_pass", "")
    if svn_pass:
        from toolbox_config import decrypt_key
        svn_pass = decrypt_key(svn_pass)
    task_id = _get_next_task_id()
    t = threading.Thread(target=_merge_query_worker,
                         args=(task_id, source_url, start_date, end_date,
                               author, keyword,
                               svn_user or None, svn_pass or None),
                         daemon=True)
    t.start()
    return jsonify({"task_id": task_id})


def _merge_query_worker(task_id, source_url, start_date, end_date,
                        author, keyword, svn_user, svn_pass):
    """后台查询任务线程，使用svn log --verbose 一次获取版本+文件"""
    q = _log_queues.setdefault(task_id, queue.Queue())
    ts = datetime.now().strftime("%H:%M:%S")

    def _log(msg, level="info"):
        tag = f"[{ts}][{level}]" if level != "info" else f"[{ts}]"
        q.put(f"{tag} {msg}\n")

    try:
        _log("正在查询SVN版本日志...")
        _log(f"源地址: {source_url}")
        _log(f"日期范围: {start_date} ~ {end_date}")
        if author:
            _log(f"提交者: {author}")
        if keyword:
            _log(f"关键词: {keyword}")
        _log("正在获取版本信息及变更文件（svn log --verbose）...")

        from urllib.parse import urlparse
        _FILE_EXTS = (".xlsm", ".xlsx", ".xls", ".xlsb", ".csv")
        parsed = urlparse(source_url)
        path_segments = parsed.path.strip("/").split("/")
        is_file_url = any(source_url.lower().endswith(ext) for ext in _FILE_EXTS)
        filter_str_verbose = None
        if is_file_url:
            filter_str_verbose = path_segments[-1]
            _log(f"检测到文件URL，仅显示文件: {filter_str_verbose}")
        elif len(path_segments) > 2:
            filter_str_verbose = "/" + "/".join(path_segments[2:])
            _log(f"检测到目录URL，仅显示 {filter_str_verbose}/ 下的文件")

        versions = svn_log(source_url, start_date, end_date,
                           author=author, keyword=keyword,
                           svn_user=svn_user, svn_pass=svn_pass,
                           verbose=True)

        # SVN 的 {date} 解析会向前回溯到最近有提交的日期，导致日期范围外的版本混入
        # 在 Python 端再做一次日期过滤
        before = len(versions)
        versions = [v for v in versions if v.get("date", "")[:10] >= start_date]
        if before != len(versions):
            _log(f"日期过滤: 剔除 {before - len(versions)} 个超出范围的版本")

        # 用 svn diff --summarize 过滤纯属性变更（只保留有内容变更的文件）
        filtered_revs = [v["rev"] for v in versions if isinstance(v.get("rev"), int) and v.get("files")]
        if filtered_revs:
            _auth_args = []
            if svn_user:
                _auth_args += ["--username", svn_user]
            if svn_pass:
                _auth_args += ["--password", svn_pass, "--no-auth-cache"]
            _log("正在过滤纯属性变更文件...")
            content_files = set()
            _svn = _get_svn_path()

            # svn diff --summarize 输出用正斜杠，source_url 可能是反斜杠，统一比较
            norm_url = source_url.replace("\\", "/").rstrip("/")
            for i in range(0, len(filtered_revs), 50):
                batch = filtered_revs[i:i + 50]
                rev_args = []
                for r in batch:
                    rev_args += ["-c", str(r)]
                try:
                    _r = subprocess.run(
                        [_svn, "diff", "--summarize"] + rev_args + [source_url] + _auth_args,
                        capture_output=True, timeout=60, **_get_subprocess_kwargs()
                    )
                    out = _r.stdout.decode("utf-8", errors="replace") if _r.stdout else ""
                    for line in out.strip().splitlines():
                        parts = line.strip().split(None, 1)
                        if len(parts) >= 2:
                            path = parts[1].replace("\\", "/")
                            if path.startswith(norm_url):
                                path = path[len(norm_url):].lstrip("/")
                                content_files.add(path)
                except Exception:
                    pass

            if content_files:
                # content_files 是相对路径（如 Assets/foo.xlsx）
                # svn_log 路径是仓库绝对路径（如 /D3_EA/trunk/Client/Assets/foo.xlsx）
                # 统一用 endswith 匹配相对路径的尾部
                _cf_lower = {p.lower() for p in content_files}
                removed = 0
                for v in versions:
                    orig = v.get("files", [])
                    v["files"] = []
                    for f in orig:
                        _fp = f.get("path", "").replace("\\", "/")
                        _fp_lower = _fp.lower()
                        # 直接相等 或 以 /{相对路径} 结尾 或 {相对路径} 是路径尾
                        if _fp_lower in _cf_lower or any(
                            _fp_lower.endswith("/" + cf) or _fp_lower == cf
                            for cf in _cf_lower
                        ):
                            v["files"].append(f)
                    removed += len(orig) - len(v.get("files", []))
                if removed:
                    _log(f"  已过滤 {removed} 个纯属性变更文件")

        if filter_str_verbose:
            for v in versions:
                if is_file_url:
                    repo_relative = "/" + "/".join(path_segments[2:]) if len(path_segments) > 2 else filter_str_verbose
                    v["files"] = [f for f in v.get("files", []) if repo_relative in f.get("path", "") or f.get("path", "").endswith("/" + filter_str_verbose)]
                else:
                    prefix = filter_str_verbose.rstrip("/") + "/"
                    v["files"] = [f for f in v.get("files", []) if f.get("path", "").startswith(prefix)]
            matched = sum(len(v.get("files", [])) for v in versions)
            if is_file_url and matched == 0:
                _log(f"完整路径未匹配，尝试仅按文件名 '{filter_str_verbose}' 过滤")
                for v in versions:
                    v["files"] = [f for f in v.get("files", []) if filter_str_verbose in f.get("path", "")]
        total = len(versions)
        _log(f"查询完成，共 {total} 个版本")
        if total > 0:
            file_count = sum(len(v.get("files", [])) for v in versions)
            _log(f"所有版本累计变更文件: {file_count} 个")
        result = json.dumps({"ok": True, "versions": versions, "total": total, "strip_prefix": filter_str_verbose if not is_file_url else ""})
        q.put(f"[RESULT]{result}\n")
    except RuntimeError as e:
        err = json.dumps({"ok": False, "error": str(e)})
        q.put(f"[RESULT]{err}\n")
    except Exception as e:
        err = json.dumps({"ok": False, "error": f"查询失败: {e}"})
        q.put(f"[RESULT]{err}\n")
    finally:
        _notify_task_done("语义合并查询")
        q.put(None)
        _log_queues.pop(task_id, None)


def _merge_worker(task_id, source_url, target_path, revisions, rev_file_map, files,
                  svn_user, svn_pass, exclude_paths=None):
    """后台合并任务线程（文件优先循环，每文件多 -c 合并）"""
    q = _log_queues.setdefault(task_id, queue.Queue())

    def _ts():
        return datetime.now().strftime("%H:%M:%S")

    def _log(msg, level="info"):
        t = _ts()
        tag = f"[{t}][{level}]" if level != "info" else f"[{t}]"
        q.put(f"{tag} {msg}\n")

    def _put(msg):
        q.put(f"[{_ts()}] {msg}")

    try:
        q.put(f"{'='*50}\n")
        q.put("🚀 SVN精准合并开始\n")
        q.put(f"源地址: {source_url}\n")
        q.put(f"目标路径: {target_path}\n")
        q.put(f"涉及版本: {len(revisions)} 个, 文件: {len(files)} 个\n")
        q.put(f"{'='*50}\n")

        # 合并前回退目标路径到最新版本（复用工作流 revert_svn 逻辑）
        q.put("🔄 回退目标工作副本至最新版本（冲突全量覆盖）...\n")
        svn = _get_svn_path()
        revert_step = {
            "exclude_paths": exclude_paths or [],
            "delete_unversioned": True
        }
        _revert_one_path(svn, target_path, revert_step, _put, task_id)
        q.put("\n")

        # 计算文件路径中需要裁剪的前缀（文件路径是仓库根相对路径如
        # /branches/xxx/Assets/...，需要裁剪到相对于 source_url 的路径）
        from urllib.parse import urlparse
        norm_source = source_url.replace("\\", "/")
        parsed = urlparse(norm_source)
        if parsed.scheme and len(parsed.scheme) > 1:
            # URL 格式如 http://svn/repo/branches/...
            url_path = parsed.path
        else:
            # 本地路径如 G:\D3_EA\Client → 用 svn info 获取 URL
            try:
                ri = subprocess.run([svn, "info", "--show-item", "url", source_url],
                                    capture_output=True, timeout=15,
                                    **_get_subprocess_kwargs())
                svn_url = ri.stdout.decode("utf-8", errors="replace").strip()
                if svn_url:
                    parsed = urlparse(svn_url)
                    url_path = parsed.path
                else:
                    url_path = ""
            except Exception:
                url_path = ""
        path_segs = url_path.strip("/").split("/")
        # 跳过前 2 段（仓库根路径 /svn/repo 等），保留分支路径
        strip_prefix = ("/" + "/".join(path_segs[2:]) + "/") if len(path_segs) > 2 else None
        # 同步裁剪 rev_file_map 的 key，保证与文件路径匹配
        if strip_prefix:
            new_map = {}
            for orig_path, revs in rev_file_map.items():
                if orig_path.startswith(strip_prefix):
                    new_map[orig_path[len(strip_prefix):]] = revs
                elif orig_path.startswith("/"):
                    new_map[orig_path[1:]] = revs
                else:
                    new_map[orig_path] = revs
            rev_file_map = new_map
        for f in files:
            raw = f.get("path", "")
            if strip_prefix and raw.startswith(strip_prefix):
                f["path"] = raw[len(strip_prefix):]
            elif raw.startswith("/"):
                f["path"] = raw[1:]

        total_merged = 0
        total_conflict = 0
        total_skipped = 0
        all_conflict_files = []
        total_files = len(files)
        done_count = 0

        for f in files:
            file_path = f["path"]
            file_revs = rev_file_map.get(file_path)
            if not file_revs:
                q.put(f"\n── 跳过: {file_path} (无法确定修订版本号)\n")
                total_skipped += 1
                done_count += 1
                continue
            q.put(f"\n── 合并: {file_path} (版本: {file_revs}) ──\n")
            try:
                result = svn_merge(
                    source_url, target_path, file_revs, [f],
                    svn_user=svn_user, svn_pass=svn_pass,
                    log_callback=_log,
                    global_max_rev=max(revisions) if revisions else None
                )
                total_merged += result["merged"]
                total_conflict += result["conflict"]
                total_skipped += result["skipped"]
                all_conflict_files.extend(result["conflict_files"])
            except Exception as e:
                q.put(f"  ❌ 合并失败: {file_path} → {e}\n")
            done_count += 1
            q.put(f"  📊 进度: {done_count}/{total_files}\n")

        q.put("\n" + "=" * 50 + "\n")
        q.put("📊 合并统计\n")
        q.put(f"  ✅ 合并成功: {total_merged} 个文件\n")
        q.put(f"  ⚠  源版本覆盖(冲突): {total_conflict} 个文件\n")
        q.put(f"  ⏭  跳过: {total_skipped} 个文件\n")
        if all_conflict_files:
            q.put("\n📋 冲突文件清单（已用源版本覆盖）：\n")
            for cf in all_conflict_files:
                q.put(f"  - {cf}\n")

        # 清理新增文件的 svn:mime-type（svn add 自动设置，仅影响 A 状态文件）
        try:
            sr = subprocess.run([svn, "status", target_path],
                                capture_output=True, timeout=60, **_get_subprocess_kwargs())
            status_out = _decode_svn_output(sr.stdout)
            added_files = []
            for line in status_out.splitlines():
                if len(line) >= 8 and line[0] == "A":
                    added_files.append(os.path.join(target_path, line[7:].strip()))
            cleared = 0
            for fp in added_files:
                try:
                    r = subprocess.run([svn, "propdel", "svn:mime-type", fp, "--quiet"],
                                       capture_output=True, timeout=15,
                                       **_get_subprocess_kwargs())
                    if r.returncode == 0:
                        cleared += 1
                except Exception:
                    pass
            if cleared:
                q.put(f"  已清理 {cleared} 个新增文件的 mime-type\n")
        except Exception:
            pass

        q.put(f"\n{'='*50}\n")

        # 清理已删除目录的残留空文件夹
        deleted_dirs = [f["path"] for f in files
                        if f.get("action") == "del" and not os.path.splitext(f["path"])[1]]
        if deleted_dirs:
            q.put("清理已删除目录残留...\n")
            removed = 0
            for d in deleted_dirs:
                fp = os.path.join(target_path, d)
                try:
                    if os.path.isdir(fp):
                        shutil.rmtree(fp, ignore_errors=True)
                        removed += 1
                except Exception:
                    pass
            if removed:
                q.put(f"  已清理 {removed} 个空文件夹\n")

        q.put("🔄 正在唤起SVN提交弹窗...\n")
        opened = open_commit_dialog(target_path)
        if opened:
            q.put("✅ 已打开TortoiseSVN提交弹窗，请手动确认提交\n")
        else:
            q.put("⚠ 未找到TortoiseSVN，请手动执行 svn commit\n")
        q.put("🎉 合并流程结束\n")
    except Exception as e:
        q.put(f"\n❌ 合并任务异常终止: {e}\n")
    finally:
        _notify_task_done("语义合并")
        q.put(None)
        _log_queues.pop(task_id, None)


@app.route("/api/merge/run", methods=["POST"])
def api_merge_run():
    """执行SVN精准合并"""
    data = request.get_json(force=True)
    source_url = data.get("source_url", "").strip()
    target_url_or_path = data.get("target_path", "").strip()
    revisions = data.get("revisions", [])
    rev_file_map = data.get("rev_file_map", {})
    files = data.get("files", [])
    if not source_url:
        return jsonify({"ok": False, "error": "源SVN地址不能为空"}), 400
    if not target_url_or_path:
        return jsonify({"ok": False, "error": "目标路径不能为空"}), 400
    if not revisions:
        return jsonify({"ok": False, "error": "请选择至少一个版本"}), 400
    if not files:
        return jsonify({"ok": False, "error": "请选择至少一个文件"}), 400
    target_path = resolve_target_path(target_url_or_path)
    if not target_path or not os.path.isdir(target_path):
        return jsonify({"ok": False, "error": f"目标路径 [{target_url_or_path}] 不是有效的本地工作副本路径，请输入正确的本地路径"}), 400
    cfg = load_config()
    svn_user = data.get("svn_user") or cfg.get("svn_user", "")
    svn_pass = data.get("svn_pass") or cfg.get("svn_pass", "")
    if svn_pass:
        from toolbox_config import decrypt_key
        svn_pass = decrypt_key(svn_pass)
    exclude_paths = data.get("exclude_paths") or cfg.get("merge_revert_exclude_paths", [])
    task_id = _get_next_task_id()
    t = threading.Thread(target=_merge_worker,
                         args=(task_id, source_url, target_path,
                               revisions, rev_file_map, files,
                               svn_user or None, svn_pass or None,
                               exclude_paths),
                         daemon=True)
    t.start()
    return jsonify({"task_id": task_id})


# ═══════════════════════════════════════════════════════════
# 语义分析 API
# ═══════════════════════════════════════════════════════════

@app.route("/api/merge/analyze", methods=["POST"])
def api_merge_analyze():
    """语义分析：对勾选的版本做结构化解构，输出 txt 报告"""
    data = request.get_json(force=True)
    source_url = data.get("source_url", "").strip()
    revisions = data.get("revisions", [])
    version_files = data.get("version_files", [])
    rev_file_map = data.get("rev_file_map", {})
    if not source_url:
        return jsonify({"error": "源SVN地址不能为空"}), 400
    if not revisions:
        return jsonify({"error": "请至少勾选一个版本"}), 400
    # GUID 映射路径只从源SVN地址对应的本地工作副本获取
    guid_path = resolve_svn_url_to_local(source_url)
    if not guid_path or not os.path.isdir(os.path.join(guid_path, "Assets")):
        return jsonify({"error": f"无法找到 SVN 地址 [{source_url}] 对应的本地工作副本路径（用于 GUID 映射查询），请先在设置中保存 SVN 地址映射"}), 400
    cfg = load_config()
    svn_user = cfg.get("svn_user", "")
    svn_pass = cfg.get("svn_pass", "")
    if svn_pass:
        from toolbox_config import decrypt_key
        svn_pass = decrypt_key(svn_pass)
    task_id = _get_next_task_id()
    t = threading.Thread(target=_merge_analyze_worker,
                         args=(task_id, source_url, guid_path, revisions,
                               version_files, rev_file_map,
                               svn_user or None, svn_pass or None),
                         daemon=True)
    t.start()
    return jsonify({"task_id": task_id})


def _merge_analyze_worker(task_id, source_url, target_path, revisions,
                          version_files, rev_file_map, svn_user, svn_pass):
    """后台语义分析线程"""
    q = _log_queues.setdefault(task_id, queue.Queue())

    def _log(msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        tag = f"[{ts}][{level}]" if level != "info" else f"[{ts}]"
        q.put(f"{tag} {msg}\n")

    try:
        from _merge_analyzer import analyze_source_url
        analyze_source_url(source_url, revisions, target_path,
                           version_files=version_files,
                           rev_file_map=rev_file_map,
                           svn_user=svn_user, svn_pass=svn_pass,
                           log_callback=_log)
        _log("语义分析完成")
    except Exception as e:
        import traceback
        _log(f"语义分析失败: {e}", "error")
        _log(traceback.format_exc(), "error")
    finally:
        _notify_task_done("语义分析")
        q.put(None)
        _log_queues.pop(task_id, None)


# ═══════════════════════════════════════════════════════════
# SSE 日志流
# ═══════════════════════════════════════════════════════════
@app.route("/api/log/stream/<task_id>")
def api_log_stream(task_id):
    q = _log_queues.get(task_id)
    if not q:
        return Response("data: 任务已结束\n\n", mimetype="text/event-stream")

    def _stream():
        try:
            while True:
                try:
                    line = q.get(timeout=15)
                    if line is None:
                        yield "data: [DONE]\n\n"
                        break
                    text = str(line).replace("\r\n", "\n").replace("\r", "\n")
                    yield "".join(f"data: {part}\n" for part in text.split("\n")) + "\n"
                except queue.Empty:
                    yield "data: \n\n"
        finally:
            _log_queues.pop(task_id, None)

    response = Response(stream_with_context(_stream()),
                        mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response

# ═══════════════════════════════════════════════════════════
# 更新检查 API
# ═══════════════════════════════════════════════════════════

@app.route("/api/update/check")
def api_update_check():
    from update_version import APP_VERSION, UPDATE_URL
    import urllib.request
    import json as _json

    result = {
        "current": APP_VERSION,
        "latest": None,
        "available": False,
        "force": False,
        "notes": "",
        "url": "",
        "error": None,
    }
    try:
        ver_url = UPDATE_URL.rstrip("/") + "/version.json"
        resp = urllib.request.urlopen(ver_url, timeout=5)
        remote = _json.loads(resp.read().decode("utf-8"))
        remote_ver = remote.get("version", "")
        result["latest"] = remote_ver
        result["notes"] = remote.get("notes", "")
        result["url"] = remote.get("url", "")
        result["force"] = remote.get("force", False)

        def _parse_ver(v):
            v = v.lstrip("vV")
            parts = v.split(".")
            return tuple(int(p) if p.isdigit() else 0 for p in parts)

        if remote_ver and _parse_ver(remote_ver) > _parse_ver(APP_VERSION):
            result["available"] = True
    except Exception as e:
        result["error"] = str(e)

    return jsonify(result)


# _updater.bat 内容（用于兜底重建，防止 xcopy 覆盖自身时异常丢失）
_UPDATER_BAT_CONTENT = r"""@echo off
setlocal enabledelayedexpansion
set DEB=%~dp0_update_debug.txt
echo [%DATE% %TIME%] bat start > "%DEB%"
echo [%DATE% %TIME%] dp0=%~dp0 >> "%DEB%"

set /a LN=0
for /f "tokens=*" %%a in ('type "%~dp0_update_args.txt" 2^>nul') do (
    set /a LN+=1
    if !LN!==1 set ZIP_FILE=%%a
    if !LN!==2 set TMP_DIR=%%a
    if !LN!==3 set APP_NAME=%%a
    if !LN!==4 set APP_DIR=%%a
)
set EXE_NAME=%APP_NAME%.exe
if not "!APP_DIR:~-1!"=="\" set APP_DIR=!APP_DIR!\
echo [%DATE% %TIME%] LN=%LN% ZIP_FILE=!ZIP_FILE! >> "%DEB%"
echo [%DATE% %TIME%] TMP_DIR=!TMP_DIR! >> "%DEB%"
echo [%DATE% %TIME%] APP_NAME=!APP_NAME! >> "%DEB%"
echo [%DATE% %TIME%] APP_DIR=!APP_DIR! >> "%DEB%"
echo [%DATE% %TIME%] EXE_NAME=!EXE_NAME! >> "%DEB%"

if "%ZIP_FILE%"=="" exit /b 1

echo [%DATE% %TIME%] taskkill /f /im !EXE_NAME! >> "%DEB%"
taskkill /f /im "%EXE_NAME%" 2>&1 >> "%DEB%"
set /a WAIT_TOTAL=0
:wait_loop
ping 127.0.0.1 -n 4 >nul
set /a WAIT_TOTAL+=3
tasklist /fi "IMAGENAME eq %EXE_NAME%" 2>nul | find /i "%EXE_NAME%" >nul
if errorlevel 1 (
    echo [%DATE% %TIME%] process gone after !WAIT_TOTAL!s >> "%DEB%"
    goto update_ok
)
if !WAIT_TOTAL! geq 15 (
    echo [%DATE% %TIME%] timeout !WAIT_TOTAL!s >> "%DEB%"
    goto update_fail
)
echo [%DATE% %TIME%] waiting !WAIT_TOTAL!s >> "%DEB%"
goto wait_loop

:update_fail
rd /S /Q "%TMP_DIR%" >nul 2>&1
del /F /Q "%ZIP_FILE%" >nul 2>&1
del /F /Q "%~dp0_update_args.txt" >nul 2>&1
echo [%DATE% %TIME%] update_fail >> "%DEB%"
exit /b 1

:update_ok
echo [%DATE% %TIME%] unzip >> "%DEB%"
powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TMP_DIR%' -Force" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [%DATE% %TIME%] powershell unzip fail, fallback Shell.Application >> "%DEB%"
    powershell -Command "$s=New-Object -ComObject Shell.Application;$z=$s.NameSpace('%ZIP_FILE%');$d=$s.NameSpace('%TMP_DIR%');$d.CopyHere($z.Items(),16)"
)

echo [%DATE% %TIME%] APP_DIR=!APP_DIR! >> "%DEB%"
echo [%DATE% %TIME%] src=!TMP_DIR!\!APP_NAME!\* >> "%DEB%"
echo [%DATE% %TIME%] dst=!APP_DIR! >> "%DEB%"
dir "!TMP_DIR!\!APP_NAME!" >> "%DEB%" 2>&1

xcopy /E /Y /Q "%TMP_DIR%\%APP_NAME%\*" "%APP_DIR%"
echo [%DATE% %TIME%] xcopy1 ec=!ERRORLEVEL! >> "%DEB%"
if errorlevel 1 (
    ping 127.0.0.1 -n 4 >nul
    xcopy /E /Y /Q "%TMP_DIR%\%APP_NAME%\*" "%APP_DIR%"
    echo [%DATE% %TIME%] xcopy2 ec=!ERRORLEVEL! >> "%DEB%"
)

echo [%DATE% %TIME%] cleanup >> "%DEB%"
rd /S /Q "%TMP_DIR%" >nul 2>&1
del /F /Q "%ZIP_FILE%" >nul 2>&1
del /F /Q "%~dp0_update_args.txt" >nul 2>&1

echo [%DATE% %TIME%] start new: !APP_DIR!!EXE_NAME! >> "%DEB%"
start "" "%APP_DIR%%EXE_NAME%"

echo [%DATE% %TIME%] bat done >> "%DEB%"
exit /b 0
"""


@app.route("/api/update/apply", methods=["POST"])
def api_update_apply():
    from update_version import APP_VERSION, UPDATE_URL
    import urllib.request
    import json as _json
    import tempfile

    try:
        ver_url = UPDATE_URL.rstrip("/") + "/version.json"
        resp = urllib.request.urlopen(ver_url, timeout=5)
        remote = _json.loads(resp.read().decode("utf-8"))
        zip_name = remote.get("url", "")
        if not zip_name:
            return jsonify({"ok": False, "error": "version.json 缺少 url 字段"}), 400

        from urllib.parse import quote
        zip_url = UPDATE_URL.rstrip("/") + "/" + quote(zip_name)
        tmp_dir = tempfile.mkdtemp(prefix="toolbox_update_")
        zip_path = os.path.join(tmp_dir, zip_name)

        import urllib.request as _req
        _req.urlretrieve(zip_url, zip_path)

        if getattr(sys, 'frozen', False):
            updater = os.path.join(sys._MEIPASS, "_updater.bat")
        else:
            updater = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_updater.bat")

        if not os.path.isfile(updater):
            # 兜底：_updater.bat 可能被 xcopy 覆盖自身时异常丢失，重新写入
            _bat_dir = os.path.dirname(updater)
            try:
                with open(updater, "w", newline="\r\n") as f:
                    f.write(_UPDATER_BAT_CONTENT)
                os.chmod(updater, 0o755)
            except Exception as e:
                return jsonify({"ok": False, "error": f"未找到更新器脚本且无法重建: {e}"}), 500

        import locale
        app_name = zip_name.rsplit("_v", 1)[0] if "_v" in zip_name else "策划工具箱"
        if getattr(sys, 'frozen', False):
            py_app_dir = os.path.dirname(sys.executable)
        else:
            py_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        args_file = os.path.join(os.path.dirname(updater), "_update_args.txt")
        with open(args_file, "w", encoding=locale.getpreferredencoding()) as f:
            f.write(f"{zip_path}\n{tmp_dir}\n{app_name}\n{py_app_dir}\n")
        vbs_path = os.path.join(tmp_dir, "run_update.vbs")
        with open(vbs_path, "w") as f:
            f.write(f'CreateObject("WScript.Shell").Run "cmd.exe /c ""{updater}""", 0, False\n')
        os.startfile(vbs_path)

        threading.Thread(target=lambda: (
            time.sleep(2),
            _quit_app_callback()
        ), daemon=True).start()

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 静态文件
# ═══════════════════════════════════════════════════════════


@app.route("/api/close", methods=["POST"])
def api_close():
    import ctypes
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "策划工具箱")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/static/<path:filename>")
def api_static(filename):
    return send_from_directory(_script_dir, filename)


# ═══════════════════════════════════════════════════════════
# 文字表检测 API
# ═══════════════════════════════════════════════════════════


def _resolve_exclude_default():
    """查找排除配置默认源文件：打包版在 _internal/，开发版在 toolbox_core/"""
    _parent = os.path.join(os.path.dirname(_script_dir), 'text_check_exclude_ids.txt')
    if os.path.isfile(_parent):
        return _parent
    return os.path.join(_script_dir, 'text_check_exclude_ids.txt')


@app.route("/api/text-check/exclude-config", methods=["GET"])
def api_text_check_exclude_config():
    """返回排除ID配置文件的路径（本地不存在时自动从默认创建）"""
    _local = os.path.join(os.environ.get('APPDATA', ''), 'planning-toolbox', 'text_check_exclude_ids.txt')
    _default = _resolve_exclude_default()
    if not os.path.isfile(_local):
        if os.path.isfile(_default):
            os.makedirs(os.path.dirname(_local), exist_ok=True)
            import shutil
            shutil.copy2(_default, _local)
    if os.path.isfile(_local):
        return jsonify({"path": _local, "is_local": True})
    return jsonify({"path": _default, "is_local": False})


@app.route("/api/text-check/run", methods=["POST"])
def api_text_check_run():
    """运行文字表检测（SSE 流式日志）"""
    data = request.get_json(force=True)
    file_path = data.get("file_path", "").strip()
    target_langs = data.get("target_langs", [])
    if not file_path or not os.path.isfile(file_path):
        return jsonify({"error": "文件不存在"}), 400
    task_id = _get_next_task_id()
    q = queue.Queue()

    def _run():
        q.put("开始文字表检测\n")
        q.put(f"文件: {file_path}\n\n")
        try:
            from _text_check import detect
            _lang_id_map = load_config().get("tr_lang_id_map", {})
            # 排除ID文件路径：本地不存在时自动从默认创建
            _local_exclude = os.path.join(os.environ.get('APPDATA', ''), 'planning-toolbox', 'text_check_exclude_ids.txt')
            _default_exclude = _resolve_exclude_default()
            if not os.path.isfile(_local_exclude):
                if os.path.isfile(_default_exclude):
                    import shutil
                    os.makedirs(os.path.dirname(_local_exclude), exist_ok=True)
                    shutil.copy2(_default_exclude, _local_exclude)
            _exclude_path = _local_exclude if os.path.isfile(_local_exclude) else _default_exclude
            out_path, issues = detect(file_path,
                progress_callback=lambda msg: q.put(msg),
                target_langs=target_langs if target_langs else None,
                lang_id_map=_lang_id_map,
                exclude_ids_path=_exclude_path)
            if out_path:
                q.put(f"\n✅ 检测完成！发现问题: {issues} 行\n")
                q.put(f"[输出路径] {out_path}\n")
            else:
                q.put(f"\n❌ {issues}\n")
        except Exception as e:
            import traceback
            q.put(f"\n❌ 检测失败: {e}\n")
            q.put(traceback.format_exc() + "\n")
        _notify_task_done("文字表检测")
        q.put(None)

    threading.Thread(target=_run, daemon=True).start()
    _log_queues[task_id] = q
    return jsonify({"task_id": task_id})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=18123, debug=False)
