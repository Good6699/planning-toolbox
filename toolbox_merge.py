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

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pm = os.path.join(_script_dir, "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)
sys.path.insert(0, _script_dir)

from toolbox_platform import _get_svn_path, _get_subprocess_kwargs  # noqa: E402


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
    cmd = ["log", source_url, "--xml", "-r",
           f"{{{start_date}}}:{{{end_date}}}", "--limit", "500"]
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


def svn_merge(source_url, target_wc, revision, files,
              svn_user=None, svn_pass=None, log_callback=None):
    """对选中的文件执行svn merge，使用 --accept theirs-full"""
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
        if not file_path:
            skip_count += 1
            continue
        local_file = os.path.join(target_wc, file_path)
        if not os.path.exists(local_file):
            _log(f"⏭ 跳过(本地不存在): {file_path}", "warn")
            skip_count += 1
            continue
        _log(f"  → 合并: {file_path}", "info")
        try:
            cmd = [
                svn_exe, "merge", "--accept", "theirs-full",
                "-c", str(revision), source_url, local_file
            ] + auth_args
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1,
                **_get_subprocess_kwargs()
            )
            stdout, _ = proc.communicate(timeout=120)
            if proc.returncode != 0:
                _log(f"  ⚠ 合并异常: {stdout.strip()}", "warn")
                conflict_count += 1
                conflict_files.append(file_path)
            else:
                conflict_output = stdout.strip().lower()
                if "conflict" in conflict_output or "合并冲突" in conflict_output:
                    _log(f"  ⚠ 已用源版本覆盖(冲突消解): {file_path}", "warn")
                    conflict_count += 1
                    conflict_files.append(file_path)
                else:
                    _log(f"  ✅ 合并成功: {file_path}", "ok")
                merged_count += 1
        except subprocess.TimeoutExpired:
            _log(f"  ❌ 超时: {file_path}", "error")
            skip_count += 1
        except Exception as e:
            _log(f"  ❌ 错误: {file_path} → {e}", "error")
            skip_count += 1

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
