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

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pm = os.path.join(_script_dir, "py_modules")
if not os.path.isdir(_pm):
    _pm = os.path.join(os.path.dirname(_script_dir), "py_modules")
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

app = Flask(__name__)
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
        "merge_target_history": cfg.get("merge_target_history", []),
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
    if task_id not in _cancelled_tasks:
        mode_names = {"compare": "SVN 对比", "export": "SVN 导出", "summary": "SVN 摘要"}
        _notify_task_done(mode_names.get(mode, f"SVN {mode}"))
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
        icon_path = os.path.join(_script_dir, "assets", "app_icon.ico")
        if not os.path.isfile(icon_path):
            icon_path = None
        from win11toast import toast
        toast(
            body=f"「{name}」任务已完成，点击查看结果",
            on_click=lambda args: _focus_app_window(),
            app_id="策划工具箱",
            icon=icon_path,
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
        _put(f"{prefix.get(tag, '')}{msg}\n")

    _put(f"{'='*50}\n")
    _put(f"执行工作流: {wf.get('name', '未命名')}\n")
    _put(f"共 {len(steps)} 个步骤\n\n")

    blocked = False
    for i, step in enumerate(steps):
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
                ok = _exec_merge_table(step, _put)
            elif stype == "merge_translation":
                ok = _exec_merge_translation(step, _put)
            elif stype == "export_error_code":
                ok = _exec_export_error_code(step, _put)
            elif stype == "lock_svn":
                ok = _exec_lock_svn(step, _put, task_id)
            elif stype == "unlock_svn":
                ok = _exec_unlock_svn(step, _put, task_id)
            elif stype == "open_tables":
                ok = _exec_open_tables(step, _put)
            elif stype == "revert_svn":
                ok = _exec_revert_svn(step, _put, task_id)
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
    _cancelled_tasks.discard(task_id)
    _put(None)
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
        put(f"  正在执行: {os.path.basename(tool_path)}\n")
        proc = subprocess.Popen(
            ["cmd.exe", "/c", tool_path],
            cwd=os.path.dirname(tool_path) if os.path.isdir(os.path.dirname(tool_path)) else None,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        _register_proc(proc, task_id)
        try:
            stdout_bytes, _ = proc.communicate(input=b"\n", timeout=3600)
            out_text = stdout_bytes.decode("gbk", errors="replace") if stdout_bytes else ""
            for line in out_text.splitlines():
                put(f"    {line}\n")
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


def _svn_update_with_cleanup(svn, d, put, task_id):  # noqa: C901
    """执行 svn update，遇到 E155004 锁时自动 cleanup 重试一次"""
    proc = None
    try:
        proc = subprocess.Popen([svn, "update", "--accept", "theirs-full", d],
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
                put(f"更新完成: {d}\n")
                return True
            err = stderr.strip()
            if "E155004" in err:
                put("检测到 SVN 锁，正在执行 cleanup...\n")
                cleanup_proc = subprocess.Popen(
                    [svn, "cleanup", d],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    **_get_subprocess_kwargs())
                _register_proc(cleanup_proc, task_id)
                try:
                    cleanup_proc.communicate(timeout=60)
                finally:
                    _unregister_proc(cleanup_proc, task_id)
                put("cleanup 完成，重试更新...\n")
                retry_proc = subprocess.Popen(
                    [svn, "update", "--accept", "theirs-full", d],
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
        return False


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
        proc = subprocess.Popen([svn, "lock", "--force", "-m", lock_msg, target_path],
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
                put(f"锁定失败: {stderr[-200:]}\n")
        finally:
            _unregister_proc(proc, task_id)
    except Exception as e:
        if proc:
            _unregister_proc(proc, task_id)
        put(f"锁定异常: {e}\n")
    return True


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


def _svn_decode_output(data):
    try:
        return data.decode("gbk")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _exec_revert_svn(step, put, task_id=None):
    target_path = step.get("target_path", "").strip()
    if not target_path or not os.path.exists(target_path):
        put(f"回退路径无效: {target_path}\n")
        return False
    svn = _get_svn_path()
    put(f"SVN回退: {target_path}\n")

    # 先 cleanup 确保无残留锁
    put("正在 cleanup 工作副本...\n")
    try:
        subprocess.run([svn, "cleanup", target_path],
                       capture_output=True, timeout=60,
                       **_get_subprocess_kwargs())
    except Exception:
        pass

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
        # 先清理所有 changelist 标签，避免回退后残留空分组
        put("清理 SVN changelist 标签...\n")
        try:
            subprocess.run(
                [svn, "changelist", "--remove", "--changelist", "语义合并",
                 target_path, "--depth", "infinity"],
                capture_output=True, timeout=60,
                **_get_subprocess_kwargs())
            subprocess.run(
                [svn, "changelist", "--remove", "--changelist", "本次修改",
                 target_path, "--depth", "infinity"],
                capture_output=True, timeout=60,
                **_get_subprocess_kwargs())
        except Exception:
            pass

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
    erl_script = os.path.join(script_dir, "..", "_export_error_code_erl.py")
    py_exe = sys.executable

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

        put("  [" + code + "] 客户端导出(批处理链)...\n")
        try:
            r = _sp.run(
                ["cmd", "/c", batch_file, "GameData", "ErrorMessage.xlsm"],
                cwd=lang_path,
                capture_output=True,
                encoding=locale.getpreferredencoding(), errors="replace",
                timeout=300,
                **_get_subprocess_kwargs()
            )
            if r.returncode == 0:
                std_out = (r.stdout or "").strip()
                if std_out:
                    for line in std_out.split("\n")[-5:]:
                        put("    " + line.strip() + "\n")
                put("  [" + code + "] 客户端导出成功\n")
            else:
                err = (r.stderr or r.stdout or "").strip()[:300]
                put("  [" + code + "] 客户端导出失败: " + err + "\n")
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
                    timeout=60,
                    **_get_subprocess_kwargs()
                )
                if r.returncode == 0:
                    for line in (r.stdout or "").strip().split("\n"):
                        put("    " + line.strip() + "\n")
                    put("  [" + code + "] erlang 导出成功\n")
                else:
                    err = (r.stderr or r.stdout or "").strip()[:200]
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
                  svn_user, svn_pass):
    """后台合并任务线程（文件优先循环，每文件多 -c 合并）"""
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

        q.put("🔄 更新目标工作副本至最新...\n")
        from toolbox_merge import svn_update_target
        svn_update_target(target_path, svn_user=svn_user, svn_pass=svn_pass,
                          log_callback=_log)
        q.put("\n")

        from urllib.parse import urlparse
        parsed = urlparse(source_url)
        segs = parsed.path.strip("/").split("/")
        strip_prefix = ("/" + "/".join(segs[2:]) + "/") if len(segs) > 2 else None
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
            file_revs = rev_file_map.get(file_path, revisions)
            q.put(f"\n── 合并: {file_path} (版本: {file_revs}) ──\n")
            try:
                result = svn_merge(
                    source_url, target_path, file_revs, [f],
                    svn_user=svn_user, svn_pass=svn_pass,
                    log_callback=_log
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

        q.put(f"\n{'='*50}\n")

        # 使用 svn changelist 给合并的文件打上 "语义合并" 分类标签
        svn_exe = _get_svn_path()
        merged_abs = set()
        for f in files:
            fp = f.get("path", "")
            if fp:
                merged_abs.add(os.path.abspath(os.path.join(target_path, fp)))
        if merged_abs:
            q.put("🏷️ 正在标记 changelist 分组（语义合并）...\n")
            # 扫描整个工作副本，按 merged_abs 过滤出有实际变化的文件
            changed_files = []
            try:
                r = subprocess.run(
                    [svn_exe, "status", target_path],
                    capture_output=True, timeout=60, **_get_subprocess_kwargs()
                )
                status_stdout = _decode_svn_output(r.stdout)
                changed_flags = {'M', 'A', 'R'}
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
                        p = os.path.join(target_path, p)
                    p = os.path.abspath(p)
                    if p in merged_abs:
                        changed_files.append(p)
                    else:
                        # 文件本身不在合并列表中但父目录在（merge 目录时递归创建子文件）
                        parent = os.path.dirname(p)
                        if parent in merged_abs:
                            changed_files.append(p)
            except Exception as e:
                q.put(f"   ⚠ svn status 扫描失败: {e}\n")
            if changed_files:
                temp_dir = tempfile.mkdtemp()
                try:
                    chg_file = os.path.join(temp_dir, "svn_merge_changelist.txt")
                    with open(chg_file, "w", encoding="utf-8") as tf:
                        for p in changed_files:
                            if os.path.exists(p):
                                tf.write(p + "\n")
                    subprocess.run(
                        [svn_exe, "changelist", "--remove", "--changelist", "语义合并",
                         target_path, "--depth", "infinity"],
                        capture_output=True, timeout=60,
                        **_get_subprocess_kwargs()
                    )
                    subprocess.run(
                        [svn_exe, "changelist", "语义合并", "--targets", chg_file],
                        capture_output=True, timeout=60,
                        **_get_subprocess_kwargs()
                    )
                    q.put(f"   ✅ 已标记 {len(changed_files)} 个文件为「语义合并」分组（排除 {len(merged_abs) - len(changed_files)} 个无变更文件）\n")
                except Exception as e:
                    q.put(f"   ⚠ changelist 标记异常: {e}\n")
                finally:
                    try:
                        os.unlink(chg_file)
                        os.rmdir(temp_dir)
                    except Exception:
                        pass
            else:
                q.put("   ℹ 合并的文件均无实际变化，跳过 changelist 标记\n")
        else:
            q.put("   ℹ 无合并文件，跳过 changelist 标记\n")

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
    task_id = _get_next_task_id()
    t = threading.Thread(target=_merge_worker,
                         args=(task_id, source_url, target_path,
                               revisions, rev_file_map, files,
                               svn_user or None, svn_pass or None),
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
        return Response("data: 任务不存在\n\n", mimetype="text/event-stream")

    def _stream():
        try:
            while True:
                try:
                    line = q.get(timeout=15)
                    if line is None:
                        yield "data: [DONE]\n\n"
                        break
                    yield f"data: {line}\n\n"
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

        zip_url = UPDATE_URL.rstrip("/") + "/" + zip_name
        tmp_dir = tempfile.mkdtemp(prefix="toolbox_update_")
        zip_path = os.path.join(tmp_dir, zip_name)

        import urllib.request as _req
        _req.urlretrieve(zip_url, zip_path)

        updater = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_updater.bat")
        if not os.path.isfile(updater):
            return jsonify({"ok": False, "error": "未找到更新器脚本 _updater.bat"}), 500

        subprocess.Popen([updater, zip_path, tmp_dir], shell=True)

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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=18123, debug=False)
