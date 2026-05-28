#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI SVN精准文件合并 — 后端逻辑模块
功能：SVN日志查询、变更文件分析、文件级精准合并、冲突自动解决、唤起提交弹窗
"""
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pm = os.path.join(_script_dir, "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)
sys.path.insert(0, _script_dir)

from toolbox_platform import _get_svn_path, _get_subprocess_kwargs  # noqa: E402


def _is_dir_path(path):
    """检查路径是否表示一个目录（无文件扩展名）"""
    path = path.rstrip("/")
    if not path:
        return False
    basename = os.path.basename(path)
    return "." not in basename


def _build_svn_auth_args(svn_user, svn_pass):
    args = []
    if svn_user:
        args += ["--username", svn_user]
    if svn_pass:
        args += ["--password", svn_pass, "--no-auth-cache"]
    return args


def _run_svn(cmd, timeout=120):
    svn_exe = _get_svn_path()
    full_cmd = [svn_exe] + cmd
    result = subprocess.run(
        full_cmd,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=timeout,
        **_get_subprocess_kwargs()
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"svn 返回码 {result.returncode}")
    return result.stdout


def svn_log(source_url, start_date, end_date, author=None, keyword=None,
            svn_user=None, svn_pass=None, verbose=False):
    """查询SVN提交日志，返回版本列表。verbose=True 时返回文件列表"""
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    cmd = ["log", source_url, "--xml", "-r",
           f"{{{start_date}}}:{{{end_dt.strftime('%Y-%m-%d')}}}"]
    if author:
        cmd += ["--search", author]
    keywords_list = [k.strip() for k in keyword.split(",")] if keyword else []
    if len(keywords_list) == 1:
        cmd += ["--search", keywords_list[0]]
    # multiple keywords: no --search, fetch all and filter Python-side later
    if verbose:
        cmd += ["--verbose"]
    cmd += _build_svn_auth_args(svn_user, svn_pass)
    raw = _run_svn(cmd, timeout=120)
    versions = []
    try:
        root = ET.fromstring(raw)
        for entry in root.findall(".//logentry"):
            rev = entry.get("revision", "")
            author_el = entry.find("author")
            date_el = entry.find("date")
            msg_el = entry.find("msg")
            v = {
                "rev": int(rev) if rev.isdigit() else rev,
                "author": author_el.text if author_el is not None else "",
                "date": date_el.text[:19] if date_el is not None and date_el.text else "",
                "msg": (msg_el.text or "").strip() if msg_el is not None else "",
            }
            if verbose:
                files = []
                for path_el in entry.findall(".//path"):
                    action = path_el.get("action", "M")
                    action_map = {"A": "add", "M": "mod", "D": "del"}
                    files.append({
                        "path": path_el.text or "",
                        "action": action_map.get(action, action),
                    })
                v["files"] = files
            versions.append(v)
    except ET.ParseError:
        pass
    if len(keywords_list) > 1:
        versions = [v for v in versions if any(kw in v.get("msg", "") for kw in keywords_list)]
    return versions


def svn_log_changed_files(source_url, revision, svn_user=None, svn_pass=None):
    """查询单个版本的变更文件列表"""
    cmd = ["diff", "--summarize", "-c", str(revision),
           source_url] + _build_svn_auth_args(svn_user, svn_pass)
    raw = _run_svn(cmd, timeout=60)
    files = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) < 3:
            continue
        action = line[0]
        path = line[2:].strip()
        clean_url = source_url.rstrip("/") + "/"
        if path.startswith(clean_url):
            path = path[len(clean_url):]
        action_map = {"A": "add", "M": "mod", "D": "del"}
        files.append({
            "path": path,
            "action": action_map.get(action, action),
        })
    return files


def find_wc_root(target_path):
    """查找本地工作副本根目录"""
    target_path = os.path.abspath(target_path)
    if not os.path.exists(target_path):
        return None
    try:
        cmd = [_get_svn_path(), "info", "--show-item", "wc-root", target_path]
        cmd += _get_subprocess_kwargs().get("startupinfo", [])
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=15
        )
        wc_root = result.stdout.strip()
        if wc_root and result.returncode == 0:
            return wc_root
    except Exception:
        pass
    return None


def _svn_export_add(svn_exe, source_url, revision, file_path, local_file, auth_args, log_callback):
    """用 svn export 下载新增文件 + svn add 纳入版本控制

    失败时先 revert 清状态再重试一次，确保能直接用源版本覆盖本地。
    """
    file_url = source_url.rstrip("/") + "/" + file_path
    parent_dir = os.path.dirname(local_file)
    try:
        os.makedirs(parent_dir, exist_ok=True)
    except Exception:
        pass
    ok, msg = _svn_try_export(svn_exe, file_url, revision, local_file, auth_args)
    if not ok:
        log_callback(msg, "warn")
        return False
    add_cmd = [svn_exe, "add", "--parents", "--force", "--quiet", local_file] + auth_args
    try:
        r = subprocess.run(add_cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=30, **_get_subprocess_kwargs())
        if r.returncode != 0:
            log_callback(f"  ⚠ svn add 失败: {file_path}", "warn")
            return False
    except Exception:
        log_callback(f"  ⚠ svn add 失败: {file_path}", "warn")
        return False
    _svn_strip_noise_props(svn_exe, local_file)
    return True


def _svn_try_export(svn_exe, file_url, revision, local_file, auth_args):
    """执行 svn export --force，失败时 revert 重试一次

    返回 (ok, msg)
    """
    for attempt in range(2):
        export_cmd = [svn_exe, "export", "--force",
                      "-r", str(revision), file_url, local_file] + auth_args
        try:
            proc = subprocess.Popen(
                export_cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1, **_get_subprocess_kwargs()
            )
            stdout_bytes, _ = proc.communicate(timeout=120)
            try:
                out_text = stdout_bytes.decode("utf-8")
            except UnicodeDecodeError:
                out_text = stdout_bytes.decode("gbk", errors="replace")
            if proc.returncode == 0:
                return True, ""
            if attempt == 0:
                subprocess.run(
                    [svn_exe, "revert", local_file],
                    capture_output=True, timeout=30,
                    **_get_subprocess_kwargs()
                )
                continue
            return False, f"  ⚠ 导出失败: {out_text.strip()}"
        except subprocess.TimeoutExpired:
            if attempt == 0:
                subprocess.run(
                    [svn_exe, "revert", local_file],
                    capture_output=True, timeout=30,
                    **_get_subprocess_kwargs()
                )
                continue
            return False, "  ❌ 导出超时"
        except Exception:
            if attempt == 0 and os.path.exists(local_file):
                try:
                    subprocess.run(
                        [svn_exe, "revert", local_file],
                        capture_output=True, timeout=30,
                        **_get_subprocess_kwargs()
                    )
                    continue
                except Exception:
                    pass
            return False, "  ❌ 导出异常"
    return False, "  ❌ 导出失败"


def _svn_delete_file(svn_exe, local_file, auth_args):
    """删除本地 SVN 工作副本中的文件

    先尝试 svn delete --force，失败则 revert 后重试一次。
    返回 (ok, msg)
    """
    for attempt in range(2):
        try:
            proc = subprocess.Popen(
                [svn_exe, "delete", "--force", local_file] + auth_args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1, **_get_subprocess_kwargs()
            )
            stdout_bytes, _ = proc.communicate(timeout=60)
            try:
                out_text = stdout_bytes.decode("utf-8")
            except UnicodeDecodeError:
                out_text = stdout_bytes.decode("gbk", errors="replace")
            if proc.returncode == 0:
                return True, ""
            if attempt == 0:
                # 第一次失败：先 revert 清掉本地状态，再试一次
                subprocess.run(
                    [svn_exe, "revert", local_file],
                    capture_output=True, timeout=30,
                    **_get_subprocess_kwargs()
                )
                continue
            return False, out_text.strip()
        except subprocess.TimeoutExpired:
            if attempt == 0:
                subprocess.run(
                    [svn_exe, "revert", local_file],
                    capture_output=True, timeout=30,
                    **_get_subprocess_kwargs()
                )
                continue
            return False, "超时"
        except Exception as e:
            if attempt == 0 and os.path.exists(local_file):
                try:
                    subprocess.run(
                        [svn_exe, "revert", local_file],
                        capture_output=True, timeout=30,
                        **_get_subprocess_kwargs()
                    )
                    continue
                except Exception:
                    pass
            return False, str(e)
    return False, "删除失败"


def _svn_revert_file(svn_exe, local_file):
    """执行 svn revert，清掉冲突状态

    返回 True/False
    """
    try:
        r = subprocess.run(
            [svn_exe, "revert", local_file],
            capture_output=True, timeout=30,
            **_get_subprocess_kwargs()
        )
        return r.returncode == 0
    except Exception:
        return False


def _svn_resolve_conflict(svn_exe, source_url, revision, file_path, local_file, auth_args):
    """清除 SVN 冲突/删除状态，用源版本完整替换（最后手段）

    当 revert + 重新 merge 都失败时使用。
    先 svn revert 撤销 SVN 元数据（删除/冲突标记），
    再用 svn cat 下载源版本内容覆盖本地文件，
    最后 svn resolve --accept working 确认状态。
    """
    try:
        subprocess.run(
            [svn_exe, "revert", local_file],
            capture_output=True, timeout=30,
            **_get_subprocess_kwargs()
        )
    except Exception:
        pass
    file_url = source_url.rstrip("/") + "/" + file_path
    try:
        proc = subprocess.Popen(
            [svn_exe, "cat", "-r", str(revision), file_url] + auth_args,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            **_get_subprocess_kwargs()
        )
        stdout, stderr = proc.communicate(timeout=120)
        if proc.returncode == 0:
            parent = os.path.dirname(local_file)
            if parent:
                try:
                    os.makedirs(parent, exist_ok=True)
                except Exception:
                    pass
            with open(local_file, "wb") as f:
                f.write(stdout)
    except Exception:
        return
    try:
        subprocess.run(
            [svn_exe, "resolve", "--accept", "working", local_file] + auth_args,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=30, **_get_subprocess_kwargs()
        )
    except Exception:
        pass


def _svn_merge_single_file(svn_exe, cmd, log_callback):
    """执行单个文件的 svn merge，返回 (status, stdout)

    status 取值:
      "ok"       — 合并成功，无冲突
      "conflict" — 合并成功但有冲突（已自动消解）
      "e155010"  — 找不到节点（文件未跟踪）
      "error"    — 其他错误
      "timeout"  — 超时
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1,
            **_get_subprocess_kwargs()
        )
        stdout_bytes, _ = proc.communicate(timeout=120)
        try:
            stdout = stdout_bytes.decode("utf-8")
        except UnicodeDecodeError:
            stdout = stdout_bytes.decode("gbk", errors="replace")
        if proc.returncode != 0:
            if "E155010" in stdout:
                return "e155010", stdout
            return "error", stdout
        conflict_output = stdout.strip().lower()
        if "conflict" in conflict_output or "合并冲突" in conflict_output:
            return "conflict", stdout
        return "ok", stdout
    except subprocess.TimeoutExpired:
        return "timeout", ""
    except Exception as e:
        return "error", str(e)


def _svn_strip_noise_props(svn_exe, local_file):
    """清除文件属性噪声（mergeinfo、mime-type），避免提交弹窗显示不必要的属性变更"""
    for prop in ("svn:mergeinfo", "svn:mime-type"):
        try:
            subprocess.run(
                [svn_exe, "propdel", prop, local_file] + _build_svn_auth_args(None, None),
                capture_output=True, timeout=15,
                **_get_subprocess_kwargs()
            )
        except Exception:
            pass


def _build_merge_c_args(revisions):
    """从版本号列表构建 -c 参数列表"""
    args = []
    for r in sorted(revisions):
        args += ["-c", str(r)]
    return args


def _svn_merge_with_retry(svn_exe, source_url, revisions, file_path, local_file,
                          auth_args, _log):
    """执行 svn merge (多版本) + 失败时 revert+retry + 最后手段 resolve

    返回 (merged, conflict, skip, conflict_files_added)
    """
    _log(f"  → 合并: {file_path}", "info")
    latest_rev = max(revisions)
    rev_args = _build_merge_c_args(revisions)
    cmd = [
        svn_exe, "merge", "--ignore-ancestry", "--accept", "theirs-full",
    ] + rev_args + [source_url, local_file] + auth_args
    status, out_text = _svn_merge_single_file(svn_exe, cmd, _log)
    if status == "ok":
        _log(f"  ✅ 合并成功: {file_path}", "ok")
        _svn_strip_noise_props(svn_exe, local_file)
        return 1, 0, 0, []
    if status == "conflict":
        _log(f"  ⚠ 已用源版本覆盖(冲突消解): {file_path}", "warn")
        _svn_strip_noise_props(svn_exe, local_file)
        return 1, 1, 0, [file_path]
    if status == "e155010":
        _log(f"  → 文件未跟踪，转为新增: {file_path}", "info")
        ok = _svn_export_add(svn_exe, source_url, latest_rev,
                             file_path, local_file, auth_args, _log)
        if ok:
            _log(f"  ✅ 新增文件: {file_path}", "ok")
            return 1, 0, 0, []
        return 0, 1, 0, [file_path]
    if status == "timeout":
        _log(f"  ❌ 超时: {file_path}", "error")
        return 0, 0, 1, []
    _log(f"  ⚠ 合并异常: {out_text.strip()}", "warn")
    ok = _svn_revert_file(svn_exe, local_file)
    if ok:
        _log(f"  → 已 revert，重新合并: {file_path}", "info")
        cmd2 = [
            svn_exe, "merge", "--ignore-ancestry", "--accept", "theirs-full",
        ] + rev_args + [source_url, local_file] + auth_args
        status2, out_text2 = _svn_merge_single_file(svn_exe, cmd2, _log)
        if status2 == "ok":
            _log(f"  ✅ 合并成功: {file_path}", "ok")
            _svn_strip_noise_props(svn_exe, local_file)
            return 1, 0, 0, []
        if status2 == "conflict":
            _log(f"  ⚠ 已用源版本覆盖(冲突消解): {file_path}", "warn")
            _svn_strip_noise_props(svn_exe, local_file)
            return 1, 1, 0, [file_path]
        _log(f"  ⚠ 重新合并仍失败: {out_text2.strip()}", "warn")
        _svn_resolve_conflict(svn_exe, source_url, latest_rev, file_path, local_file, auth_args)
        _svn_strip_noise_props(svn_exe, local_file)
        _log(f"  → 已用源版本强制覆盖（最后手段）: {file_path}", "warn")
    else:
        _svn_resolve_conflict(svn_exe, source_url, latest_rev, file_path, local_file, auth_args)
        _svn_strip_noise_props(svn_exe, local_file)
        _log(f"  → revert 失败，已用源版本强制覆盖: {file_path}", "warn")
    return 0, 1, 0, [file_path]


def _svn_merge_one_file(svn_exe, source_url, revisions, file_path, local_file,
                        action, auth_args, _log):
    """处理单个文件的 add/del/mod merge（多版本合并）

    目录新增/删除也走 svn merge 让 SVN 递归处理整个目录树。
    目录属性修改（mergeinfo 等）直接跳过。
    返回 (merged, conflict, skip, conflict_files_added)
    """
    is_dir = _is_dir_path(file_path)
    latest_rev = max(revisions)

    # 目录属性修改 → 跳过（mergeinfo 等噪声）
    if is_dir and action == "mod":
        _log(f"  ℹ 跳过目录属性变更: {file_path}", "info")
        return 1, 0, 0, []

    # 目录新增 → svn export 递归下载整个目录 + svn add 纳入跟踪
    if is_dir and action == "add":
        _log(f"  → 新增目录: {file_path}", "info")
        file_url = source_url.rstrip("/") + "/" + file_path
        ok, msg = _svn_try_export(svn_exe, file_url, latest_rev, local_file, auth_args)
        if not ok:
            _log(msg, "warn")
            return 0, 1, 0, [file_path]
        try:
            r = subprocess.run(
                [svn_exe, "add", "--parents", "--force", "--quiet", local_file] + auth_args,
                capture_output=True, timeout=30,
                **_get_subprocess_kwargs()
            )
            if r.returncode != 0:
                _log(f"  ⚠ svn add 失败: {file_path}", "warn")
                return 0, 1, 0, [file_path]
        except Exception:
            _log(f"  ⚠ svn add 失败: {file_path}", "warn")
            return 0, 1, 0, [file_path]
        _svn_strip_noise_props(svn_exe, local_file)
        _log(f"  ✅ 新增目录: {file_path}", "ok")
        return 1, 0, 0, []

    # 文件新增 → export + add（用最新版本）
    if action == "add" and not is_dir:
        _log(f"  → 新增: {file_path}", "info")
        ok = _svn_export_add(svn_exe, source_url, latest_rev,
                             file_path, local_file, auth_args, _log)
        if ok:
            _svn_strip_noise_props(svn_exe, local_file)
            _log(f"  ✅ 新增文件: {file_path}", "ok")
            return 1, 0, 0, []
        return 0, 1, 0, [file_path]

    # 文件删除 → delete --force
    if action == "del" and not is_dir:
        if not os.path.exists(local_file):
            _log(f"  ▶ 文件已被删除，跳过: {file_path}", "info")
            return 1, 0, 0, []
        _log(f"  → 删除: {file_path}", "info")
        ok, msg = _svn_delete_file(svn_exe, local_file, auth_args)
        if ok:
            _log(f"  ✅ 已删除: {file_path}", "ok")
            return 1, 0, 0, []
        _log(f"  ⚠ 删除失败: {msg}", "warn")
        return 0, 1, 0, [file_path]

    # 目录删除 + 文件修改：统一走 svn merge
    if action != "add" and not os.path.exists(local_file):
        _log(f"⏭ 跳过(本地不存在): {file_path}", "warn")
        return 0, 0, 1, []

    return _svn_merge_with_retry(
        svn_exe, source_url, revisions, file_path, local_file,
        auth_args, _log)


def svn_merge(source_url, target_wc, revisions, files,
              svn_user=None, svn_pass=None, log_callback=None):
    """对选中的文件执行svn merge（多版本合并），使用 --accept theirs-full"""
    def _log(msg, level="info"):
        if log_callback:
            log_callback(msg, level)

    svn_exe = _get_svn_path()
    auth_args = _build_svn_auth_args(svn_user, svn_pass)
    merged_count = 0
    conflict_count = 0
    skip_count = 0
    conflict_files = []

    for f in files:
        file_path = f.get("path", "")
        action = f.get("action", "mod")
        if not file_path:
            skip_count += 1
            continue
        local_file = os.path.join(target_wc, file_path)
        m, c, s, cf = _svn_merge_one_file(
            svn_exe, source_url, revisions, file_path, local_file,
            action, auth_args, _log)
        merged_count += m
        conflict_count += c
        skip_count += s
        conflict_files.extend(cf)

    return {
        "merged": merged_count,
        "conflict": conflict_count,
        "skipped": skip_count,
        "conflict_files": conflict_files,
    }


def open_commit_dialog(target_wc):
    """唤起TortoiseSVN提交弹窗"""
    proc_path = None
    candidates = [
        r"C:\Program Files\TortoiseSVN\bin\TortoiseProc.exe",
        r"C:\Program Files (x86)\TortoiseSVN\bin\TortoiseProc.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            proc_path = p
            break
    if not proc_path:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\TortoiseSVN") as key:
                path, _ = winreg.QueryValueEx(key, "ProcPath")
                if path and os.path.exists(path):
                    proc_path = path
        except (OSError, FileNotFoundError):
            pass
    if not proc_path:
        return False
    try:
        subprocess.Popen(
            [proc_path, "/command:commit", f"/path:{target_wc}",
             "/notempfile", "/closeonend:2"],
            **_get_subprocess_kwargs()
        )
        return True
    except Exception:
        return False


def resolve_target_path(target_url_or_path):
    """解析目标路径：如果是URL，尝试找到对应的本地工作副本"""
    if os.path.exists(target_url_or_path):
        return os.path.abspath(target_url_or_path)
    wc_root = find_wc_root(target_url_or_path)
    if wc_root:
        return wc_root
    return None


def resolve_svn_url_to_local(url, cfg=None):
    """根据 SVN URL 查找对应的本地工作副本路径

    查找顺序：
    1. svn_url_mappings 配置（精确匹配 / 前缀匹配）
    2. 候选路径（output_dir_history + 非http svn_urls）逐级 svn info --show-item url
    3. 遍历各盘（C盘最后）前 3 级目录搜索匹配的 .svn 工作副本
    返回: 本地路径字符串，或 None
    """
    if not url:
        return None
    clean_url = url.rstrip("/")

    if cfg is None:
        from toolbox_config import load_config
        cfg = load_config()

    # 1. 查 svn_url_mappings 映射表
    mappings = cfg.get("svn_url_mappings", {})
    if clean_url in mappings:
        p = mappings[clean_url]
        if os.path.isdir(p):
            return os.path.normpath(p)
    # 前缀匹配：URL 是 mapping key 的子路径
    for map_url, local_path in mappings.items():
        if clean_url.startswith(map_url.rstrip("/") + "/"):
            rel = clean_url[len(map_url.rstrip("/")) + 1:]
            full = os.path.join(local_path, rel.replace("/", os.sep))
            if os.path.isdir(full):
                return os.path.normpath(full)

    # 2. 候选路径逐级匹配
    candidates = set()
    for d in cfg.get("merge_target_history", []):
        if d:
            candidates.add(d)
    for d in cfg.get("output_dir_history", []):
        if d:
            candidates.add(d)
    for u in cfg.get("svn_urls", []):
        if u and not u.startswith("http"):
            candidates.add(u)
    svn_exe = _get_svn_path()
    for c in candidates:
        d = os.path.normpath(c)
        while True:
            try:
                r = subprocess.run(
                    [svn_exe, "info", "--show-item", "url", d],
                    capture_output=True, text=True, timeout=5,
                    **_get_subprocess_kwargs()
                )
                wc_url = r.stdout.strip() if r.returncode == 0 else ""
                if wc_url and (clean_url == wc_url or clean_url.startswith(wc_url + "/")):
                    return os.path.normpath(d)
            except Exception:
                pass
            parent = os.path.dirname(d)
            if parent == d or not parent:
                break
            d = parent

    # 3. 遍历各盘
    return _scan_drives_for_svn_wc(clean_url, svn_exe)


def _scan_drives_for_svn_wc(url, svn_exe=None):
    """遍历所有盘符（C盘最后），查前3级目录中匹配该 URL 的 SVN 工作副本"""
    if not url:
        return None
    if svn_exe is None:
        svn_exe = _get_svn_path()
    # D-Z 在前，C 盘最后
    drives = [f"{c}:\\" for c in "DEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")]
    drives.append("C:\\")
    # 最多 3 级子目录
    for root in drives:
        try:
            for entry in os.listdir(root):
                first = os.path.join(root, entry)
                if not os.path.isdir(first) or first.startswith("C:\\") and entry.lower() in ("windows", "program files", "program files (x86)", "programdata", "users", "$recycle.bin", "system volume information"):
                    continue
                if os.path.isdir(os.path.join(first, ".svn")):
                    try:
                        r = subprocess.run(
                            [svn_exe, "info", "--show-item", "url", first],
                            capture_output=True, text=True, timeout=5,
                            **_get_subprocess_kwargs()
                        )
                        wc_url = r.stdout.strip() if r.returncode == 0 else ""
                        if wc_url and (url == wc_url or url.startswith(wc_url + "/")):
                            return os.path.normpath(first)
                    except Exception:
                        pass
                # 第2级
                if os.path.isdir(first):
                    try:
                        for e2 in os.listdir(first):
                            second = os.path.join(first, e2)
                            if not os.path.isdir(second):
                                continue
                            if os.path.isdir(os.path.join(second, ".svn")):
                                try:
                                    r = subprocess.run(
                                        [svn_exe, "info", "--show-item", "url", second],
                                        capture_output=True, text=True, timeout=5,
                                        **_get_subprocess_kwargs()
                                    )
                                    wc_url = r.stdout.strip() if r.returncode == 0 else ""
                                    if wc_url and (url == wc_url or url.startswith(wc_url + "/")):
                                        return os.path.normpath(second)
                                except Exception:
                                    pass
                            # 第3级
                            try:
                                for e3 in os.listdir(second):
                                    third = os.path.join(second, e3)
                                    if not os.path.isdir(third):
                                        continue
                                    if os.path.isdir(os.path.join(third, ".svn")):
                                        try:
                                            r = subprocess.run(
                                                [svn_exe, "info", "--show-item", "url", third],
                                                capture_output=True, text=True, timeout=5,
                                                **_get_subprocess_kwargs()
                                            )
                                            wc_url = r.stdout.strip() if r.returncode == 0 else ""
                                            if wc_url and (url == wc_url or url.startswith(wc_url + "/")):
                                                return os.path.normpath(third)
                                        except Exception:
                                            pass
                            except (PermissionError, OSError):
                                pass
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError):
            pass
    return None


def migrate_old_svn_mappings(cfg):
    """从旧配置 history 中挖掘 URL↔路径映射，补充到 svn_url_mappings

    遍历 merge_target_history + output_dir_history + 非http svn_urls，
    对每个路径执行 svn info --show-item url 获取对应 URL，
    建立 URL→本地路径 映射。
    返回是否新增了映射项。
    """
    if not cfg:
        return False
    mappings = cfg.get("svn_url_mappings", {})
    if not mappings:
        mappings = {}
    before = len(mappings)
    svn_exe = _get_svn_path()
    candidates = set()
    for d in cfg.get("merge_target_history", []):
        if d:
            candidates.add(os.path.normpath(d))
    for d in cfg.get("output_dir_history", []):
        if d:
            candidates.add(os.path.normpath(d))
    for u in cfg.get("svn_urls", []):
        if u and not u.startswith("http"):
            candidates.add(os.path.normpath(u))
    for d in sorted(candidates):
        if not os.path.isdir(d):
            continue
        try:
            r = subprocess.run(
                [svn_exe, "info", "--show-item", "wc-root", d],
                capture_output=True, text=True, timeout=5,
                **_get_subprocess_kwargs()
            )
            wc_root = r.stdout.strip() if r.returncode == 0 else ""
            if not wc_root:
                continue
            r2 = subprocess.run(
                [svn_exe, "info", "--show-item", "url", wc_root],
                capture_output=True, text=True, timeout=5,
                **_get_subprocess_kwargs()
            )
            wc_url = r2.stdout.strip() if r2.returncode == 0 else ""
            if wc_url and wc_url not in mappings:
                mappings[wc_url.rstrip("/")] = os.path.normpath(wc_root)
        except Exception:
            pass
    if len(mappings) > before:
        cfg["svn_url_mappings"] = mappings
        try:
            from toolbox_config import save_config
            save_config(cfg)
        except Exception:
            pass
        return True
    return False
