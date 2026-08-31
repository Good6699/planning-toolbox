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
    # --non-interactive：凭证失效时快速失败而非交互等待（GUI 环境挂起 5 分钟）
    args = ["--non-interactive"]
    if svn_user:
        args += ["--username", svn_user]
    if svn_pass:
        args += ["--password", svn_pass, "--no-auth-cache"]
    return args


def _svn_decode_output(data):
    try:
        return data.decode("gbk")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _svn_quote_url(arg):
    """SVN URL 参数 percent-encode（空格→%20、$→%24 等），保留 URL 结构字符。
    非 URL 参数（本地路径、文件名等）原样返回。分支名可能含空格/特殊字符，
    未编码的 URL 传给 svn 会报 E170013/E215004。"""
    if isinstance(arg, str) and (arg.startswith("http://") or arg.startswith("https://") or arg.startswith("svn://")):
        from urllib.parse import quote
        return quote(arg, safe=":/?&=%@#+.,;~")
    return arg


def _run_svn(cmd, timeout=120, cancel_check=None):
    svn_exe = _get_svn_path()
    full_cmd = [svn_exe] + [_svn_quote_url(a) for a in cmd]
    # Popen + 轮询：cancel_check 命中（任务手动终止）或超时则 kill，避免 svn 命令继续跑
    proc = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        **_get_subprocess_kwargs())
    import time as _t
    _start = _t.time()
    while True:
        try:
            out, err = proc.communicate(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if cancel_check and cancel_check():
                proc.kill()
                proc.communicate()
                raise RuntimeError("任务已取消")
            if _t.time() - _start > timeout:
                proc.kill()
                proc.communicate()
                raise RuntimeError("svn 命令超时")
    if proc.returncode != 0:
        try:
            err = err.decode("gbk")
        except UnicodeDecodeError:
            err = err.decode("utf-8", errors="replace")
        raise RuntimeError(err.strip() or f"svn 返回码 {proc.returncode}")
    try:
        return out.decode("gbk")
    except UnicodeDecodeError:
        return out.decode("utf-8", errors="replace")


def _parse_svn_date(text):
    """将 SVN XML 格式的 UTC 时间 (2026-05-29T13:05:56.123456Z) 转为本地时间字符串"""
    try:
        text = text.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        local = dt.astimezone()
        return local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return text[:19] if text else ""


def svn_log(source_url, start_date, end_date, author=None, keyword=None,
            svn_user=None, svn_pass=None, verbose=False, use_merge_history=False,
            cancel_check=None):
    """查询SVN提交日志，返回版本列表。verbose=True 时返回文件列表；
    use_merge_history=True 时追溯合并来源（merge 历史版本）；
    cancel_check 用于手动终止（命中则 kill svn 命令）"""
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    cmd = ["log", source_url, "--xml", "-r",
           f"{{{start_date}}}:{{{end_dt.strftime('%Y-%m-%d')}}}"]
    author_list = [a.strip() for a in str(author or "").split(",") if a.strip()]
    # --search 与 --use-merge-history 组合会输出损坏 XML（返回 0 版本），
    # merge 历史模式走全量 + Python 端作者过滤（与关键词处理一致）
    if author_list and not use_merge_history:
        # 多个 --search 是或关系（svn >= 1.9），配合 Python 端过滤精确匹配
        for a in author_list:
            cmd += ["--search", a]
    keywords_list = [k.strip() for k in keyword.split(",")] if keyword else []
    # 关键词（单个或多个）加 --search 预过滤（svn 多 --search 是或关系，匹配提交备注），
    # Python 端再按提交备注精确过滤（大小写不敏感）。
    # 注意：--search 与 --use-merge-history 组合在 svn 端会返回 0，merge 历史模式走全量 + Python 过滤
    if keywords_list and not use_merge_history:
        for kw in keywords_list:
            cmd += ["--search", kw]
    if verbose:
        cmd += ["--verbose"]
    if use_merge_history:
        cmd += ["--use-merge-history"]
    cmd += _build_svn_auth_args(svn_user, svn_pass)
    raw = _run_svn(cmd, timeout=300, cancel_check=cancel_check)
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
                "date": _parse_svn_date(date_el.text) if date_el is not None and date_el.text else "",
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
                        # copyfrom 合并/复制信息（svn copy / svn merge 复制）：来源路径与版本
                        "copyfrom_path": path_el.get("copyfrom-path") or "",
                        "copyfrom_rev": path_el.get("copyfrom-rev") or "",
                    })
                v["files"] = files
            versions.append(v)
    except ET.ParseError:
        pass
    # 作者过滤：逗号分隔多选，包含匹配，或关系
    if author_list:
        versions = [v for v in versions if any(a in (v.get("author") or "") for a in author_list)]
    # 关键词过滤：提交备注包含任一关键词（逗号分隔多选，大小写不敏感，或关系）
    if keywords_list:
        _kws_lower = [kw.lower() for kw in keywords_list]
        versions = [v for v in versions if any(kw in (v.get("msg") or "").lower() for kw in _kws_lower)]
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
            cmd, capture_output=True, timeout=15
        )
        if result.returncode != 0:
            wc_root = ""
        else:
            try:
                wc_root = result.stdout.decode("gbk").strip()
            except UnicodeDecodeError:
                wc_root = result.stdout.decode("utf-8", errors="replace").strip()
            return wc_root
    except Exception:
        pass
    return None


def _svn_export_add(svn_exe, source_url, revision, file_path, local_file, auth_args, log_callback, cancel_check=None,
                    file_url_override=None):
    """用 svn export 下载新增文件 + svn add 纳入版本控制

    失败时先 revert 清状态再重试一次，确保能直接用源版本覆盖本地。
    merge 来源版本文件由调用方传 file_url_override（完整仓库 URL）。
    """
    file_url = file_url_override or (source_url.rstrip("/") + "/" + file_path)
    parent_dir = os.path.dirname(local_file)
    try:
        os.makedirs(parent_dir, exist_ok=True)
    except Exception:
        pass
    ok, msg = _svn_try_export(svn_exe, file_url, revision, local_file, auth_args, cancel_check)
    if not ok:
        log_callback(msg, "warn")
        return False
    add_cmd = [svn_exe, "add", "--parents", "--force", "--quiet", local_file] + auth_args
    try:
        r = subprocess.run(add_cmd, capture_output=True, timeout=30, **_get_subprocess_kwargs())
        if r.returncode != 0:
            log_callback(f"  ⚠ svn add 失败: {file_path}", "warn")
            return False
    except Exception:
        log_callback(f"  ⚠ svn add 失败: {file_path}", "warn")
        return False
    return True


def _svn_try_export(svn_exe, file_url, revision, local_file, auth_args, cancel_check=None):
    """执行 svn export --force，失败时 revert 重试一次；cancel_check 命中即中止

    返回 (ok, msg)
    """
    import time as _t
    for attempt in range(2):
        export_cmd = [svn_exe, "export", "--force",
                      "-r", str(revision), _svn_quote_url(file_url), local_file] + auth_args
        try:
            proc = subprocess.Popen(
                export_cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1, **_get_subprocess_kwargs()
            )
            _start = _t.time()
            while True:
                try:
                    stdout_bytes, _ = proc.communicate(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    if cancel_check and cancel_check():
                        proc.kill()
                        proc.communicate()
                        return False, "任务已取消"
                    if _t.time() - _start > 120:
                        proc.kill()
                        proc.communicate()
                        return False, "export 超时"
            try:
                out_text = stdout_bytes.decode("gbk")
            except UnicodeDecodeError:
                out_text = stdout_bytes.decode("utf-8", errors="replace")
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
                out_text = stdout_bytes.decode("gbk")
            except UnicodeDecodeError:
                out_text = stdout_bytes.decode("utf-8", errors="replace")
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


def _svn_resolve_conflict(svn_exe, source_url, revision, file_path, local_file, auth_args, global_max_rev=None, log_callback=None):
    """用源版本完整替换本地文件（最后手段）

    先 resolve 清除树冲突，再 svn cat 下载覆盖写入。
    global_max_rev: 所有选中版本的最大值，用于 svn cat 确保取到最新内容
    """
    # 先清除冲突标记，否则 svn cat 对本地路径会失败
    try:
        subprocess.run(
            [svn_exe, "resolve", "--accept", "working", local_file] + auth_args,
            capture_output=True, timeout=30,
            **_get_subprocess_kwargs()
        )
    except Exception:
        pass
    cat_rev = global_max_rev if global_max_rev is not None else revision
    file_url = source_url.rstrip("/") + "/" + file_path
    for _attempt in range(2):
        try:
            proc = subprocess.Popen(
                [svn_exe, "cat", "-r", str(cat_rev), _svn_quote_url(file_url)] + auth_args,
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
                # 清除只读/隐藏/系统属性后写文件
                subprocess.run(["attrib", "-R", "-S", "-H", local_file],
                               capture_output=True, timeout=15)
                with open(local_file, "wb") as f:
                    f.write(stdout)
                break
            else:
                err_text = _svn_decode_output(stderr)[:200] if stderr else ("返回码 " + str(proc.returncode))
                log_callback("⚠ svn cat第" + str(_attempt + 1) + "次失败 (" + str(cat_rev) + "): " + err_text, "error")
                if _attempt == 0:
                    log_callback("🔄 1秒后重试...", "info")
                    import time
                    time.sleep(1)
        except subprocess.TimeoutExpired:
            log_callback("❌ svn cat第" + str(_attempt + 1) + "次超时 (rev " + str(cat_rev) + ", 120s): " + file_path, "error")
            if _attempt == 0:
                log_callback("🔄 1秒后重试...", "info")
                import time
                time.sleep(1)
        except Exception as e:
            log_callback("❌ svn cat第" + str(_attempt + 1) + "次异常: " + str(e), "error")
            if _attempt == 0:
                log_callback("🔄 1秒后重试...", "info")
                import time
                time.sleep(1)
    try:
        subprocess.run(
            [svn_exe, "add", "--force", "--quiet", local_file] + auth_args,
            capture_output=True, timeout=30,
            **_get_subprocess_kwargs()
        )
    except Exception:
        pass
    try:
        subprocess.run(
            [svn_exe, "resolve", "--accept", "working", local_file] + auth_args,
            capture_output=True, timeout=30,
            **_get_subprocess_kwargs()
        )
    except Exception:
        pass


def _svn_merge_single_file(svn_exe, cmd, log_callback):
    """执行单个文件的 svn merge，返回 (status, stdout)

    status 取值:
      "ok"       — 合并成功，无冲突
      "conflict" — 合并成功但有冲突（已自动消解）
      "e155010"  — 找不到节点（文件未跟踪）
      "tree_working" — tree conflict 不能 accept theirs-full，需改用来源版本覆盖
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
            stdout = stdout_bytes.decode("gbk")
        except UnicodeDecodeError:
            stdout = stdout_bytes.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            safe_cmd = []
            hide_next = False
            for part in cmd:
                if hide_next:
                    safe_cmd.append("***")
                    hide_next = False
                    continue
                safe_cmd.append(str(part))
                if str(part).lower() == "--password":
                    hide_next = True
            detail = stdout.strip() or "输出为空"
            detail = "svn merge 返回码: " + str(proc.returncode) + "\n命令: " + " ".join(safe_cmd) + "\n" + detail
            if "E155010" in stdout:
                return "e155010", detail
            if "E155027" in stdout or "Tree conflict can only be resolved to 'working'" in stdout:
                return "tree_working", detail
            return "error", detail
        conflict_output = stdout.strip().lower()
        if "conflict" in conflict_output or "合并冲突" in conflict_output:
            return "conflict", stdout
        return "ok", stdout
    except subprocess.TimeoutExpired:
        return "timeout", ""
    except Exception as e:
        return "error", str(e)


def _build_merge_c_args(revisions):
    """从版本号列表构建 -c 参数列表"""
    args = []
    for r in sorted(revisions):
        args += ["-c", str(r)]
    return args


def _svn_merge_with_retry(svn_exe, source_url, revisions, file_path, local_file,
                          auth_args, _log, global_max_rev=None, cancel_check=None,
                          file_url_override=None):
    """将文件直接覆盖为源仓库最新版本（HEAD），不再逐版本合并

    global_max_rev: 源仓库 HEAD 版本号（svn_merge 传入），用于 export 时取最新内容
    merge 来源版本文件由调用方传 file_url_override（完整仓库 URL）。
    返回 (merged, conflict, skip, conflict_files_added)
    """
    head_rev = global_max_rev or (max(revisions) if revisions else None)
    if head_rev is None:
        _log(f"  ❌ 无法确定最新版本号: {file_path}", "error")
        return 0, 0, 1, []
    _log(f"  → 覆盖为最新版(r{head_rev}): {file_path}", "info")
    file_url = file_url_override or (source_url.rstrip("/") + "/" + file_path)

    # 1) summarize 快速检查：无任何差异（内容+属性）直接跳过
    try:
        dr = subprocess.run(
            [svn_exe, "diff", "--summarize", _svn_quote_url(file_url + "@HEAD"), local_file] + auth_args,
            capture_output=True, timeout=30, **_get_subprocess_kwargs())
        if dr.returncode == 0 and not (dr.stdout or b"").strip():
            _log(f"  ℹ 最新版与本地无差异，跳过: {file_path}", "info")
            return 1, 0, 0, []
    except Exception:
        pass
    # 2) summarize 有差异（可能只是属性差异）→ 内容级比较：svn cat vs 本地字节
    try:
        cat_r = subprocess.run(
            [svn_exe, "cat", _svn_quote_url(file_url + "@HEAD")] + auth_args,
            capture_output=True, timeout=180, **_get_subprocess_kwargs())
        if cat_r.returncode == 0:
            with open(local_file, "rb") as _f:
                _local = _f.read()
            if cat_r.stdout == _local:
                _log(f"  ℹ 仅属性差异（内容相同），跳过: {file_path}", "info")
                return 0, 0, 1, []
    except Exception:
        pass

    ok, msg = _svn_try_export(svn_exe, file_url, head_rev, local_file, auth_args, cancel_check)
    if ok:
        _log(f"  ✅ 已覆盖为最新版: {file_path}", "ok")
        return 1, 0, 0, []
    _log(f"  ⚠ 覆盖失败: {msg}", "warn")
    return 0, 1, 0, [file_path]


def _sync_add_meta(svn_exe, source_url, file_path, local_file, auth_args, _log,
                   file_url_override=None):
    """新增文件时联动同路径 .meta：源存在则保证目标 .meta 内容与源一致

    目标 .meta 缺失 → 写入并 svn add；存在但 GUID 不一致 → 用源覆盖（变 M）。
    merge 来源版本文件由调用方传 file_url_override（完整仓库 URL）。
    """
    if file_path.lower().endswith(".meta"):
        return
    file_url = file_url_override or (source_url.rstrip("/") + "/" + file_path)
    meta_url = file_url + ".meta"
    meta_local = local_file + ".meta"
    meta_rel = file_path + ".meta"
    import re as _re
    try:
        r = subprocess.run(
            [svn_exe, "cat", _svn_quote_url(meta_url)] + auth_args,
            capture_output=True, timeout=60, **_get_subprocess_kwargs())
    except Exception:
        return
    if r.returncode != 0:
        return  # 源仓库没有该 .meta，跳过
    src_meta = r.stdout
    m = _re.search(rb'guid:\s*([0-9a-f]+)', src_meta)
    src_guid = m.group(1).decode() if m else ""
    if os.path.exists(meta_local):
        try:
            with open(meta_local, "rb") as f:
                mb = _re.search(rb'guid:\s*([0-9a-f]+)', f.read())
        except Exception:
            return
        tgt_guid = mb.group(1).decode() if mb else ""
        if tgt_guid == src_guid:
            return  # 内容一致，跳过
        try:
            with open(meta_local, "wb") as f:
                f.write(src_meta)
        except Exception as e:
            _log(f"  ⚠ .meta 覆盖失败: {meta_rel} → {e}", "warn")
            return
        _log(f"  ⚠ 已同步 .meta（GUID 不一致）: {meta_rel}", "warn")
    else:
        try:
            os.makedirs(os.path.dirname(meta_local), exist_ok=True)
            with open(meta_local, "wb") as f:
                f.write(src_meta)
            subprocess.run(
                [svn_exe, "add", "--parents", "--force", "--quiet", meta_local] + auth_args,
                capture_output=True, timeout=30, **_get_subprocess_kwargs())
            _log(f"  ⚠ 已联动新增 .meta: {meta_rel}", "warn")
        except Exception as e:
            _log(f"  ⚠ .meta 写入失败: {meta_rel} → {e}", "warn")


def _svn_merge_one_file(svn_exe, source_url, revisions, file_path, local_file,
                        action, auth_args, _log, global_max_rev=None, cancel_check=None,
                        file_url_override=None):
    """处理单个文件的 add/del/mod（整文件覆盖为源仓库最新版本 HEAD）

    目录新增/删除也走 export/add 让 SVN 递归处理整个目录树。
    目录属性修改（mergeinfo 等）直接跳过。
    merge 来源版本的文件（copyfrom）由调用方传入 file_url_override（完整仓库 URL），
    下载源直接用来源路径的文件，目标位置仍为裁剪后的相对路径。
    返回 (merged, conflict, skip, conflict_files_added)
    """
    is_dir = _is_dir_path(file_path)
    head_rev = global_max_rev or (max(revisions) if revisions else None)

    # 目录属性修改 → 跳过（mergeinfo 等噪声）
    if is_dir and action == "mod":
        _log(f"  ℹ 跳过目录属性变更: {file_path}", "info")
        return 0, 0, 1, []

    # 目录新增 → svn export 递归下载整个目录 + svn add 纳入跟踪
    if is_dir and action == "add":
        _log(f"  → 新增目录: {file_path}", "info")
        file_url = file_url_override or (source_url.rstrip("/") + "/" + file_path)
        ok, msg = _svn_try_export(svn_exe, file_url, head_rev, local_file, auth_args, cancel_check)
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
        _log(f"  ✅ 新增目录: {file_path}", "ok")
        return 1, 0, 0, []

    # 文件新增 → export + add（用最新版本），并联动同路径 .meta
    if action == "add" and not is_dir:
        _log(f"  → 新增: {file_path}", "info")
        if os.path.exists(local_file):
            # 目标已存在（merge 来源版本映射场景）：已跟踪 → 按最新版覆盖；未跟踪 → 走 export+add
            try:
                _st = subprocess.run(
                    [svn_exe, "info", local_file], capture_output=True, timeout=15,
                    **_get_subprocess_kwargs())
                if _st.returncode == 0:
                    return _svn_merge_with_retry(
                        svn_exe, source_url, revisions, file_path, local_file,
                        auth_args, _log, global_max_rev, cancel_check,
                        file_url_override=file_url_override)
            except Exception:
                pass
        ok = _svn_export_add(svn_exe, source_url, head_rev,
                             file_path, local_file, auth_args, _log, cancel_check,
                             file_url_override=file_url_override)
        if ok:
            _sync_add_meta(svn_exe, source_url, file_path, local_file, auth_args, _log,
                           file_url_override=file_url_override)
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

    # 目录删除 → delete --force
    if action == "del" and is_dir:
        if not os.path.exists(local_file):
            _log(f"  ▶ 目录已被删除，跳过: {file_path}", "info")
            return 1, 0, 0, []
        _log(f"  → 删除目录: {file_path}", "info")
        ok, msg = _svn_delete_file(svn_exe, local_file, auth_args)
        if ok:
            _log(f"  ✅ 已删除目录: {file_path}", "ok")
            return 1, 0, 0, []
        _log(f"  ⚠ 删除目录失败: {msg}", "warn")
        return 0, 1, 0, [file_path]

    # 本地不存在时改按新增处理，直接 export + add，并联动同路径 .meta
    if action not in ("add", "del") and not os.path.exists(local_file):
        _log(f"  → 本地不存在，改按新增: {file_path}", "info")
        ok = _svn_export_add(svn_exe, source_url, head_rev,
                             file_path, local_file, auth_args, _log, cancel_check)
        if ok:
            _sync_add_meta(svn_exe, source_url, file_path, local_file, auth_args, _log)
            _log(f"  ✅ 新增文件: {file_path}", "ok")
            return 1, 0, 0, []
        return 0, 1, 0, [file_path]

    return _svn_merge_with_retry(
        svn_exe, source_url, revisions, file_path, local_file,
        auth_args, _log, global_max_rev, cancel_check)


def svn_update_target(target_path, svn_user=None, svn_pass=None, log_callback=None):
    """对目标工作副本执行 svn update --accept theirs-full --force"""
    def _log(msg, level="info"):
        if log_callback:
            log_callback(msg, level)
    svn_exe = _get_svn_path()
    auth_args = _build_svn_auth_args(svn_user, svn_pass)
    cmd = [
        svn_exe, "update", "--accept", "theirs-full", "--force",
        target_path
    ] + auth_args
    _log("  → 执行: svn update --accept theirs-full --force", "info")
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=300, **_get_subprocess_kwargs()
        )
        if result.returncode != 0:
            try:
                err = result.stderr.decode("gbk")
            except UnicodeDecodeError:
                err = result.stderr.decode("utf-8", errors="replace")
            try:
                out = result.stdout.decode("gbk")
            except UnicodeDecodeError:
                out = result.stdout.decode("utf-8", errors="replace")
            _log(f"  ⚠ svn update 返回码 {result.returncode}: "
                 f"{err.strip() or out.strip()}", "warn")
        else:
            _log("  ✅ svn update 完成", "ok")
    except subprocess.TimeoutExpired:
        _log("  ❌ svn update 超时(300s)", "error")
    except Exception as e:
        _log(f"  ❌ svn update 异常: {e}", "error")


def svn_merge(source_url, target_wc, revisions, files,
              svn_user=None, svn_pass=None, log_callback=None,
              global_max_rev=None, cancel_check=None):
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

    # 2026-08-27: 合并改为取源仓库最新版本（HEAD），不按勾选版本号逐版本合并
    head_rev = global_max_rev
    if not head_rev:
        try:
            _r = subprocess.run(
                [svn_exe, "info", "--show-item", "revision", _svn_quote_url(source_url)] + auth_args,
                capture_output=True, timeout=30, **_get_subprocess_kwargs())
            _txt = _r.stdout.decode("utf-8", errors="replace").strip()
            head_rev = int(_txt) if _txt.isdigit() else None
        except Exception:
            head_rev = None
    if not head_rev and revisions:
        head_rev = max(revisions)
    if head_rev:
        _log(f"  使用源仓库最新版本: r{head_rev}（不按勾选版本号合并）", "info")

    for f in files:
        file_path = f.get("path", "")
        action = f.get("action", "mod")
        if not file_path:
            skip_count += 1
            continue
        local_file = os.path.join(target_wc, file_path)
        m, c, s, cf = _svn_merge_one_file(
            svn_exe, source_url, revisions, file_path, local_file,
            action, auth_args, _log, head_rev, cancel_check,
            file_url_override=f.get("src_url") or None)
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
             "/notempfile", "/closeonend:0"],
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


_wc_map_cache = {"t": 0.0, "map": {}}


def collect_svn_working_copies():
    """遍历各盘（C盘最后）前3级目录，收集所有 SVN 工作副本 URL→本地路径 映射

    一次遍历供批量匹配多个 URL，避免逐个 URL 全盘搜索；结果缓存 5 分钟。
    返回: {url: 本地路径}
    """
    import time as _time
    if _time.time() - _wc_map_cache["t"] < 300:
        return _wc_map_cache["map"]
    wc_map = {}
    svn_exe = _get_svn_path()
    drives = [f"{c}:\\" for c in "DEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")]
    drives.append("C:\\")
    for root in drives:
        try:
            for entry in os.listdir(root):
                first = os.path.join(root, entry)
                if not os.path.isdir(first):
                    continue
                if first.startswith("C:\\") and entry.lower() in (
                        "windows", "program files", "program files (x86)",
                        "programdata", "users", "$recycle.bin", "system volume information"):
                    continue
                if os.path.isdir(os.path.join(first, ".svn")):
                    try:
                        r = subprocess.run(
                            [svn_exe, "info", "--show-item", "url", first],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
                            **_get_subprocess_kwargs())
                        if r.returncode == 0 and r.stdout.strip():
                            wc_map[r.stdout.strip().rstrip("/")] = os.path.normpath(first)
                    except Exception:
                        pass
                try:
                    for e2 in os.listdir(first):
                        second = os.path.join(first, e2)
                        if not os.path.isdir(second):
                            continue
                        if os.path.isdir(os.path.join(second, ".svn")):
                            try:
                                r = subprocess.run(
                                    [svn_exe, "info", "--show-item", "url", second],
                                    capture_output=True, encoding="utf-8", errors="replace", timeout=5,
                                    **_get_subprocess_kwargs())
                                if r.returncode == 0 and r.stdout.strip():
                                    wc_map[r.stdout.strip().rstrip("/")] = os.path.normpath(second)
                            except Exception:
                                pass
                        try:
                            for e3 in os.listdir(second):
                                third = os.path.join(second, e3)
                                if not os.path.isdir(third):
                                    continue
                                if os.path.isdir(os.path.join(third, ".svn")):
                                    try:
                                        r = subprocess.run(
                                            [svn_exe, "info", "--show-item", "url", third],
                                            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
                                            **_get_subprocess_kwargs())
                                        if r.returncode == 0 and r.stdout.strip():
                                            wc_map[r.stdout.strip().rstrip("/")] = os.path.normpath(third)
                                    except Exception:
                                        pass
                        except (PermissionError, OSError):
                            pass
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass
    _wc_map_cache["t"] = _time.time()
    _wc_map_cache["map"] = wc_map
    return wc_map


