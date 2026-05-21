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
import concurrent.futures
from datetime import datetime

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pm = os.path.join(_script_dir, "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)
sys.path.insert(0, _script_dir)

from flask import Flask, render_template, request, jsonify, Response, send_from_directory, stream_with_context  # noqa: E402
from toolbox_config import (  # noqa: E402
    SCRIPT_DIR, MAIN_SCRIPT, DEFAULT_OUTPUT_DIR,
    load_config, save_config,
)
from toolbox_platform import _get_subprocess_kwargs, _get_svn_path, _check_office_lock  # noqa: E402
from xlsm_zipper import apply_via_excel  # noqa: E402
from toolbox_merge import svn_log, svn_log_changed_files, svn_merge, open_commit_dialog, resolve_target_path  # noqa: E402

if len(sys.argv) >= 2 and sys.argv[1] == "--worker":
    if len(sys.argv) < 3:
        print("Usage: --worker <worker_script> [args...]", file=sys.stderr)
        sys.exit(1)
    worker_script = sys.argv[2]
    worker_args = sys.argv[3:]
    env = os.environ.copy()
    pm = os.path.join(_script_dir, "py_modules")
    if os.path.isdir(pm):
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pm if not existing else pm + os.pathsep + existing
    q = queue.Queue()
    proc = subprocess.Popen(
        [sys.executable, worker_script] + worker_args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        bufsize=1, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    for line in iter(proc.stdout.readline, ""):
        q.put(line)
    proc.wait()
    q.put(None)
    sys.exit(proc.returncode)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


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


def _register_proc(proc, task_id=None):
    _active_subprocesses.append(proc)
    if task_id:
        _active_tasks.setdefault(task_id, []).append(proc)


def _unregister_proc(proc, task_id=None):
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
        cmd += ["--keyword", keyword]
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
                                text=True, encoding="utf-8", errors="replace",
                                bufsize=1, **_get_subprocess_kwargs())
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

    procs = _active_tasks.pop(task_id, [])
    for proc in procs:
        try:
            proc.kill()
            proc.communicate(timeout=5)
        except Exception:
            pass
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
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk", errors="replace")


def _svn_update_first(q, target_dir):
    svn_exe = _get_svn_path()
    q.put("正在更新 SVN 工作副本...\n")
    try:
        r = subprocess.run(
            [svn_exe, "update", "--accept", "theirs-full", target_dir],
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


def _run_svn_after_upload(q, target_dir, copied_files):  # noqa: C901
    q.put(f"\n{'─'*40}\n")
    q.put("开始SVN上传\n")

    svn_exe = _get_svn_path()
    result = subprocess.run(
        [svn_exe, "info", target_dir],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15, **_get_subprocess_kwargs()
    )
    if result.returncode != 0:
        q.put("⚠️ 目标目录没有找到SVN链接，跳过\n")
        return

    svn_url = ""
    for line in result.stdout.splitlines():
        if line.startswith("URL: "):
            svn_url = line[5:]
            break
    wc_r = subprocess.run(
        [svn_exe, "info", "--show-item", "wc-root", target_dir],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15, **_get_subprocess_kwargs()
    )
    wc_root = wc_r.stdout.strip() if wc_r.returncode == 0 else ""
    q.put(f"   ✅ SVN 链接验证通过，即将提交 {len(copied_files)} 个文件\n")

    if svn_url and wc_root:
        q.put("   📄 上传文件 SVN 路径:\n")
        for f in copied_files:
            rel = os.path.relpath(f, wc_root).replace("\\", "/")
            q.put(f"       {svn_url}/{rel}\n")

    try:
        r_status = subprocess.run(
            [svn_exe, "status", "--no-ignore", wc_root],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, **_get_subprocess_kwargs()
        )
        if r_status.returncode == 0:
            copied_abs = {os.path.abspath(f) for f in copied_files}
            revert_list = []
            for line in r_status.stdout.splitlines():
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
                        capture_output=True, text=True, timeout=10, **_get_subprocess_kwargs()
                    )
                q.put(f"   🧹 已清理 {len(revert_list)} 个未提交的 add 记录\n")
    except Exception:
        pass

    add_ok = 0
    for f in copied_files:
        try:
            r = subprocess.run(
                [svn_exe, "add", "--parents", "--force", "--quiet", os.path.abspath(f)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, **_get_subprocess_kwargs()
            )
            if r.returncode == 0:
                add_ok += 1
        except Exception:
            pass
    q.put(f"   ✅ {add_ok}/{len(copied_files)} 个文件已添加到SVN版本控制\n")

    to_add = []
    to_commit = []
    changed_flags = {'M', 'A', 'R', '!', '?'}
    try:
        r_st = subprocess.run(
            [svn_exe, "status", wc_root],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, **_get_subprocess_kwargs()
        )
        if r_st.returncode == 0:
            copied_abs = {os.path.abspath(f) for f in copied_files}
            for line in r_st.stdout.splitlines():
                if not line or len(line) < 2:
                    continue
                flag = line[0]
                if flag not in changed_flags:
                    continue
                status_path = line[7:].strip() if len(line) > 7 else ""
                if not status_path:
                    continue
                if not os.path.isabs(status_path):
                    status_path = os.path.join(wc_root, status_path)
                status_path = os.path.abspath(status_path)
                if status_path in copied_abs:
                    if flag in ('A', '?', '!'):
                        to_add.append(status_path)
                    else:
                        to_commit.append(status_path)
    except Exception:
        pass

    modified_files = to_add + to_commit
    try:
        r_cl = subprocess.run(
            [svn_exe, "status", "--changelist", "本次修改", wc_root],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, **_get_subprocess_kwargs()
        )
        if r_cl.returncode == 0:
            modified_now = set(modified_files)
            cl_clean = []
            for line in r_cl.stdout.splitlines():
                if not line or len(line) < 2:
                    continue
                flag = line[0]
                status_path = line[7:].strip() if len(line) > 7 else ""
                if not status_path:
                    continue
                if not os.path.isabs(status_path):
                    status_path = os.path.join(wc_root, status_path)
                status_path = os.path.abspath(status_path)
                if flag not in changed_flags or status_path not in modified_now:
                    cl_clean.append(status_path)
            if cl_clean:
                for cf in cl_clean:
                    subprocess.run(
                        [svn_exe, "changelist", "--remove", cf],
                        capture_output=True, text=True, timeout=10, **_get_subprocess_kwargs()
                    )
                q.put(f"   🧹 已从changelist清理 {len(cl_clean)} 个文件\n")
    except Exception:
        pass

    if not modified_files:
        q.put("⚠️ 没有文件实际发生变化，跳过SVN上传\n")
        return

    cl_ok = 0
    for f in modified_files:
        try:
            r = subprocess.run(
                [svn_exe, "changelist", "本次修改", os.path.abspath(f)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, **_get_subprocess_kwargs()
            )
            if r.returncode == 0:
                cl_ok += 1
        except Exception:
            pass
    q.put(f"   🏷️ {cl_ok}/{len(modified_files)} 个文件已标记 changelist\n")

    tortoise = _get_tortoise_proc_path()
    if tortoise:
        q.put(f"🖥️ 正在打开 TortoiseSVN 提交对话框 ({len(modified_files)} 个文件)...\n")
        subprocess.Popen([tortoise, "/command:commit", f"/path:{wc_root}"])
        q.put("✅ TortoiseSVN 提交对话框已打开\n")
    else:
        q.put("⚠️ 未找到 TortoiseSVN\n")


def _run_upload_copy(src, tgt, files, q):
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
                else:
                    os.makedirs(target_dir, exist_ok=True)
                for root, dirs, fnames in os.walk(sp):
                    rel = os.path.relpath(root, sp)
                    dst_dir = os.path.join(target_dir, rel)
                    os.makedirs(dst_dir, exist_ok=True)
                    for fn in fnames:
                        dst = os.path.join(dst_dir, fn)
                        _copy_file_upload(os.path.join(root, fn), dst)
                        copied_files.append(dst)
                q.put(f"✓ {name}/ 文件夹已复制\n")
            else:
                dst = os.path.join(tgt, name)
                _copy_file_upload(sp, dst)
                copied_files.append(dst)
                q.put(f"✓ {name}\n")
            success += 1
        except Exception as e:
            fail += 1
            q.put(f"✗ {name}: {e}\n")
    q.put(f"\n── 文件复制完成: {success} 成功, {fail} 失败 ──\n")

    if success > 0:
        _run_svn_after_upload(q, tgt, copied_files)

    q.put(None)


def _copy_file_upload(src_p, dst_p):
    os.makedirs(os.path.dirname(dst_p), exist_ok=True)
    if os.path.isfile(dst_p):
        os.chmod(dst_p, stat.S_IWRITE)
    shutil.copy2(src_p, dst_p)


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
    threading.Thread(target=_run_upload_copy, args=(src, tgt, files, q), daemon=True).start()
    return jsonify({"task_id": task_id})

# ═══════════════════════════════════════════════════════════
# 工作流 API
# ═══════════════════════════════════════════════════════════


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


def _run_wf_task(q, wf, steps, task_id):
    prefix = {"error": "❌ ", "ok": "✓ ", "warn": "⚠ ", "head": ""}

    def _put(msg, tag=""):
        q.put(msg)

    def _line(msg, tag=""):
        _put(f"{prefix.get(tag, '')}{msg}\n")

    _put(f"{'='*50}\n")
    _put(f"执行工作流: {wf.get('name', '未命名')}\n")
    _put(f"共 {len(steps)} 个步骤\n\n")

    blocked = False
    for i, step in enumerate(steps):
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
                ok = _exec_merge_table(step, _put)
            elif stype == "merge_translation":
                ok = _exec_merge_translation(step, _put)
            elif stype == "export_error_code":
                ok = _exec_export_error_code(step, _put)
            elif stype == "lock_svn":
                ok = _exec_lock_svn(step, _put, task_id)
            elif stype == "open_tables":
                ok = _exec_open_tables(step, _put)
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
    _put(None)


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
    tools = step.get("tools", [])
    if input_file and not os.path.exists(input_file):
        put(f"输入文件无效: {input_file}\n")
        return False
    if not tools:
        put("未配置工具，跳过\n")
        return True
    put(f"输入文件: {os.path.basename(input_file) if input_file else 'N/A'}\n")
    put(f"使用 {len(tools)} 个工具并行执行...\n")

    def _run_one(tool_path):
        proc = subprocess.Popen(
            ["cmd.exe", "/c", tool_path],
            cwd=os.path.dirname(tool_path) if os.path.isdir(os.path.dirname(tool_path)) else None,
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE)
        _register_proc(proc, task_id)
        try:
            proc.communicate(input=b"\n", timeout=3600)
            put(f"  {os.path.basename(tool_path)} 已完成\n")
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tools)) as executor:
        futures = [executor.submit(_run_one, t) for t in tools]
        concurrent.futures.wait(futures)

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


def _exec_lock_svn(step, put, task_id=None):
    target_path = step.get("target_path", "").strip()
    lock_msg = step.get("lock_msg", "锁定中，请勿修改")
    if not target_path or not os.path.isfile(target_path):
        put(f"锁定目标无效: {target_path}\n")
        return False
    svn = _get_svn_path()
    put(f"SVN 锁定: {target_path}\n")
    proc = None
    try:
        proc = subprocess.Popen([svn, "lock", "--force", "-m", lock_msg, target_path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, **_get_subprocess_kwargs())
        _register_proc(proc, task_id)
        try:
            stdout, stderr = proc.communicate(timeout=60)
            if proc.returncode == 0:
                put("锁定成功\n")
                return True
            else:
                put(f"锁定失败: {stderr[-200:]}\n")
        finally:
            _unregister_proc(proc, task_id)
    except Exception as e:
        if proc:
            _unregister_proc(proc, task_id)
        put(f"锁定异常: {e}\n")
    return True


def _exec_open_tables(step, put):
    file_paths = step.get("file_paths", [])
    if not file_paths:
        put("没有要打开的文件\n")
        return True
    for fp in file_paths:
        fp = fp.strip()
        if not fp or not os.path.exists(fp):
            put(f"文件不存在: {fp}\n")
            continue
        try:
            os.startfile(fp)
            put(f"打开: {os.path.basename(fp)}\n")
        except Exception as e:
            put(f"无法打开 {fp}: {e}\n")
    return True


def _exec_export_error_code(step, put):
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

    import subprocess as _sp
    script_dir = os.path.dirname(os.path.abspath(__file__))
    et2_path = os.path.join(script_dir, "ExcelTool2.py")
    et2_python = sys.executable

    results = []

    for code in codes:
        lang_path = os.path.join(lang_dir, code)
        xlsm_file = os.path.join(lang_path, "Data2", "ErrorMessage.xlsm")

        if not os.path.isfile(xlsm_file):
            results.append((code, False, "ErrorMessage.xlsm 未找到"))
            put("  [" + code + "] SKIP: xlsm 未找到\n")
            continue

        cmd = [et2_python, et2_path, "ErrorMessage", "--lang-dir", lang_path]
        try:
            r = _sp.run(cmd, capture_output=True, text=True, timeout=120,
                        **_get_subprocess_kwargs())
            if r.returncode == 0:
                last_line = r.stdout.strip().split("\n")[-1]
                put("  [" + code + "] " + last_line + "\n")
                results.append((code, True, "导出成功"))
            else:
                err = (r.stderr or r.stdout or "").strip()[:200]
                put("  [" + code + "] FAIL: " + err + "\n")
                results.append((code, False, err))
        except Exception as e:
            put("  [" + code + "] ERROR: " + str(e) + "\n")
            results.append((code, False, str(e)))

    ok_count = sum(1 for _, ok, _ in results if ok)
    put("导出错误码完成: " + str(ok_count) + "/" + str(len(codes)) + "\n")
    if ok_count == len(codes):
        put("全部语言导出成功\n")
    return ok_count == len(codes)


def _exec_merge_translation(step, put):  # noqa: C901
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


def _exec_merge_table(step, put):
    put("合并表格功能请使用桌面版\n")
    return True

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

            numbered = [f"{i+1}|{t.replace(chr(13), ' ').replace(chr(10), ' ')}" for i, t in enumerate(texts)]
            user_parts.append(
                f"请将以下文本从 {clean_src} 一次性翻译为 {lang_display}。"
                f"\n严格按照编号和分隔符格式返回，每行一条："
                f"\n编号|翻译1|翻译2|翻译3..."
                f"\n不要包含任何额外说明、解释或空行。"
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
                                    parts = [p.strip() for p in m.group(2).split("|")]
                                    row_result = {}
                                    for ti, tgt in enumerate(tgt_names):
                                        if ti < len(parts) and parts[ti]:
                                            row_result[tgt] = parts[ti]
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
            for row in ws.iter_rows(min_row=2, values_only=False):
                src_val = row[src_col - 1].value
                if src_val is None or not str(src_val).strip():
                    continue
                src_text = str(src_val).strip()

                missing_targets = set()
                for tgt_name, tgt_col in tgt_col_map.items():
                    tgt_val = row[tgt_col - 1].value
                    if tgt_val and str(tgt_val).strip():
                        continue
                    if not has_raw:
                        ref_val = all_refs.get(tgt_name, {}).get(src_text)
                        if ref_val:
                            ws.cell(row=row[0].row, column=tgt_col, value=ref_val)
                            ref_matched += 1
                            continue
                    missing_targets.add(tgt_name)

                if missing_targets:
                    batch_items.append((row[0].row, src_text, missing_targets))

            q.put(f"参考匹配直接填入: {ref_matched} 条\n")
            q.put(f"需要 API 翻译: {len(batch_items)} 条 -> {len(tgt_names)} 个语言\n")

            if not batch_items:
                q.put("无需 API 翻译，全部已处理\n")
                wb.save(out_path)
                wb.close()
                q.put(f"已保存: {out_path}\n")
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
                    _time.sleep(1)
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
                _time.sleep(0.5)

            wb.save(out_path)
            wb.close()
            q.put(f"{'='*50}\n")
            q.put(f"[输出路径] {out_dir}\n")
            q.put(f"翻译完成! 输出文件: {out_path}\n")
        except PermissionError:
            q.put("翻译过程出错: 输出文件被占用，请关闭 Excel 中已打开的文件后重试\n")
        except Exception as e:
            import traceback
            q.put(f"翻译过程出错: {e}\n")
            q.put(traceback.format_exc() + "\n")
        q.put(None)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/open/folder", methods=["POST"])
def api_open_folder():
    data = request.get_json(force=True)
    path = data.get("path", "").strip()
    if path and os.path.isdir(path):
        try:
            os.startfile(path)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "路径无效"}), 400


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
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
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
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace",
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
    """根据 SVN URL 查找对应的本地工作副本路径（不打开资源管理器）"""
    cfg = load_config()
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
                    capture_output=True, text=True, timeout=5
                )
                wc_url = r.stdout.strip() if r.returncode == 0 else ""
                if wc_url and (url == wc_url or url.startswith(wc_url + "/")):
                    rel = url[len(wc_url):].lstrip("/")
                    wc = subprocess.run(
                        ["svn", "info", "--show-item", "wc-root", d],
                        capture_output=True, text=True, timeout=5
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
        r = subprocess.run(
            [svn_exe, "changelist", "--remove", "--changelist", "本次修改", target_dir, "--depth", "infinity"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, **_get_subprocess_kwargs()
        )
        if r.returncode == 0:
            return jsonify({"ok": True, "message": "changelist 已清理"})
        return jsonify({"ok": False, "error": r.stderr.strip() or "清理失败"})
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
    """查询源SVN版本列表及变更文件"""
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
    try:
        versions = svn_log(source_url, start_date, end_date,
                           author=author, keyword=keyword,
                           svn_user=svn_user or None,
                           svn_pass=svn_pass or None)
        for v in versions:
            try:
                files = svn_log_changed_files(
                    source_url, v["rev"],
                    svn_user=svn_user or None,
                    svn_pass=svn_pass or None)
                v["files"] = files
            except Exception:
                v["files"] = []
        return jsonify({"ok": True, "versions": versions, "total": len(versions)})
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": f"查询失败: {e}"}), 200


def _merge_worker(task_id, source_url, target_path, revisions, files,
                  svn_user, svn_pass):
    """后台合并任务线程"""
    q = _log_queues.setdefault(task_id, queue.Queue())
    ts = datetime.now().strftime("%H:%M:%S")

    def _log(msg, level="info"):
        tag = f"[{ts}][{level}]" if level != "info" else f"[{ts}]"
        q.put(f"{tag} {msg}\n")

    try:
        q.put(f"{'='*50}\n")
        q.put("🚀 SVN精准合并开始\n")
        q.put(f"源地址: {source_url}\n")
        q.put(f"目标路径: {target_path}\n")
        q.put(f"涉及版本: {len(revisions)} 个, 文件: {len(files)} 个\n")
        q.put(f"{'='*50}\n")

        total_merged = 0
        total_conflict = 0
        total_skipped = 0
        all_conflict_files = []

        for rev in revisions:
            q.put(f"\n── 处理版本 r{rev} ──\n")
            try:
                result = svn_merge(
                    source_url, target_path, rev, files,
                    svn_user=svn_user, svn_pass=svn_pass,
                    log_callback=_log
                )
                total_merged += result["merged"]
                total_conflict += result["conflict"]
                total_skipped += result["skipped"]
                all_conflict_files.extend(result["conflict_files"])
            except Exception as e:
                q.put(f"  ❌ 版本 r{rev} 合并失败: {e}\n")

        q.put("\n" + "=" * 50 + "\n")
        q.put("📊 合并统计\n")
        q.put(f"  ✅ 合并成功: {total_merged} 个文件\n")
        q.put(f"  ⚠  源版本覆盖(冲突): {total_conflict} 个文件\n")
        q.put(f"  ⏭  跳过: {total_skipped} 个文件\n")
        if all_conflict_files:
            q.put("\n📋 冲突文件清单（已用源版本覆盖）：\n")
            for cf in all_conflict_files:
                q.put(f"  - {cf}\n")

        q.put(f"\n{'='*50}\n")
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
        q.put(None)


@app.route("/api/merge/run", methods=["POST"])
def api_merge_run():
    """执行SVN精准合并"""
    data = request.get_json(force=True)
    source_url = data.get("source_url", "").strip()
    target_url_or_path = data.get("target_path", "").strip()
    revisions = data.get("revisions", [])
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
    if not target_path:
        return jsonify({"ok": False, "error": "无法确定目标本地工作副本路径，请确保路径有效或已执行过SVN检出"}), 400
    cfg = load_config()
    svn_user = data.get("svn_user") or cfg.get("svn_user", "")
    svn_pass = data.get("svn_pass") or cfg.get("svn_pass", "")
    if svn_pass:
        from toolbox_config import decrypt_key
        svn_pass = decrypt_key(svn_pass)
    task_id = _get_next_task_id()
    t = threading.Thread(target=_merge_worker,
                         args=(task_id, source_url, target_path,
                               revisions, files,
                               svn_user or None, svn_pass or None),
                         daemon=True)
    t.start()
    return jsonify({"task_id": task_id})


# ═══════════════════════════════════════════════════════════
# SSE 日志流
# ═══════════════════════════════════════════════════════════
@app.route("/api/log/stream/<task_id>")
def api_log_stream(task_id):
    q = _log_queues.get(task_id)
    if not q:
        return Response("data: 任务不存在\n\n", mimetype="text/event-stream")

    def _stream():
        while True:
            try:
                line = q.get(timeout=15)
                if line is None:
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {line}\n\n"
            except queue.Empty:
                yield "data: \n\n"

    response = Response(stream_with_context(_stream()),
                        mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response

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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=18123, debug=False)
