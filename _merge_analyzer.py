#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SVN 语义变更分析模块 — 独立于合并逻辑的纯净分析引擎"""
import os
import sys
import re
import subprocess
import tempfile
import pickle
import time
from datetime import datetime
from urllib.parse import urlparse

_script_dir = os.path.dirname(os.path.abspath(__file__))
_pm = os.path.join(_script_dir, "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)
sys.path.insert(0, _script_dir)

from toolbox_platform import _get_svn_path, _get_subprocess_kwargs  # noqa: E402

# ── Unity YAML 组件类型号 → 中文名称映射 ──
_COMPONENT_NAMES = {
    "1": "GameObject/节点",
    "4": "Transform",
    "20": "Camera",
    "23": "MeshRenderer",
    "33": "MeshFilter",
    "48": "Animator",
    "95": "AnimatorStateMachine",
    "114": "MonoBehaviour/脚本",
    "198": "ParticleSystem",
    "199": "ParticleSystemRenderer",
    "212": "SpriteRenderer",
    "213": "Sprite",
    "222": "RectTransform",
    "223": "Canvas",
    "224": "CanvasRenderer",
    "225": "CanvasScaler",
    "226": "GraphicRaycaster",
}

# ── 图片/材质/字体/脚本 引用字段名 → 中文名 ──
_GUID_FIELDS = {
    "m_Sprite": "Sprite/图片",
    "m_Texture": "Texture/贴图",
    "m_Icon": "Icon/图标",
    "m_Image": "Image/图片",
    "m_Material": "Material/材质",
    "m_Script": "MonoBehaviour/脚本",
    "m_Prefab": "Prefab/预制体引用",
    "m_Controller": "Controller/控制器",
    "m_Font": "Font/字体",
    "m_FontAsset": "FontAsset/字体资产",
    "m_Animation": "Animation/动画剪辑",
}

# ── 人类可读的 Unity 属性名映射 ──
_PROPERTY_NAMES = {
    "m_Name": "名称",
    "m_LocalPosition": "坐标 position",
    "m_LocalRotation": "旋转 rotation",
    "m_LocalScale": "缩放 scale",
    "m_Text": "文本内容",
    "m_FontSize": "字号",
    "m_FontSizeBase": "基础字号",
    "m_Color": "颜色",
    "m_Enabled": "启用状态",
    "m_Width": "宽度",
    "m_Height": "高度",
    "m_AnchorMin": "锚点最小值",
    "m_AnchorMax": "锚点最大值",
    "m_Pivot": "轴心",
    "m_SizeDelta": "尺寸偏移",
    "m_RaycastTarget": "射线检测",
    "m_IsActive": "激活状态",
    "m_Alpha": "透明度",
    "m_Spacing": "间距",
    "m_LineSpacing": "行间距",
    "m_Alignment": "对齐方式",
    "m_HorizontalOverflow": "水平溢出",
    "m_VerticalOverflow": "垂直溢出",
}

# ── 正则表达式 ──
_GUID_IN_TEXT_RE = re.compile(r'guid:\s*([a-f0-9]{32})')
_YAML_BLOCK_ADD_RE = re.compile(r'^\+--- !u!(\d+)', re.MULTILINE)
_YAML_BLOCK_DEL_RE = re.compile(r'^---- !u!(\d+)', re.MULTILINE)
_NODE_NAME_RE = re.compile(r'^[+-]\s+m_Name:\s*(.+)', re.MULTILINE)
_PROP_CHANGE_RE = re.compile(r'^([+-])\s+(m_\w+):\s*(.+)')
_CS_METHOD_RE = re.compile(r'^\+{1,3}\s+(public|private|protected|internal)\s+(void|string|int|float|bool|double|class|struct|enum|interface)\s+(\w+)')
_CS_ADD_LINE_RE = re.compile(r'^\+[^+]')
_OLD_NEW_PAIR_RE = re.compile(r'^-\s+(m_\w+):\s*(.+)\n\+\s+\1:\s*(.+)', re.MULTILINE)


# ═══════════════════════════════════════════════════════════
# SVN 工具函数
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
# GUID → 资产路径 映射（按需搜索）
# ═══════════════════════════════════════════════════════════

def _find_meta_for_guids(guid_set, target_path):
    """按 guid 集合在 target_path/Assets/ 中查找 .meta 文件，返回 {guid → 相对路径}"""
    if not guid_set:
        return {}
    assets_dir = os.path.join(target_path, "Assets")
    if not os.path.isdir(assets_dir):
        return {}
    result = {}
    remaining = set(guid_set)
    for root, dirs, files in os.walk(assets_dir):
        dirs[:] = [d for d in dirs if d not in ("Library", "Temp", "obj", "Obj", "Plugin", "Plugins")]
        if not remaining:
            break
        for fname in files:
            if not fname.endswith(".meta"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    head = fh.read(500)
                for guid in list(remaining):
                    if f"guid: {guid}" in head:
                        asset_rel = os.path.relpath(fpath[:-5], target_path).replace("\\", "/")
                        result[guid] = asset_rel
                        remaining.discard(guid)
                        if not remaining:
                            return result
            except Exception:
                pass
    return result


def _extract_guids_from_diff(diff_text):
    """从 diff 文本中提取所有引用的 guid"""
    return set(_GUID_IN_TEXT_RE.findall(diff_text))


def _resolve_guid(guid, guid_map):
    """GUID 转资产相对路径，查不到返回空字符串"""
    return guid_map.get(guid, "")


# ═══════════════════════════════════════════════════════════
# .prefab / .unity 语义解析
# ═══════════════════════════════════════════════════════════

def _collect_node_names(diff_text):
    """从 diff 文本中统计节点名和 fileID 的映射"""
    names = {}
    for m in _NODE_NAME_RE.finditer(diff_text):
        name = m.group(1).strip().strip("\"'")
        if name:
            names[name] = name
    return names


def _parse_prefab_diff(diff_text, guid_map):
    """解析 .prefab/.unity 的 diff 文本，返回语义变更描述列表"""
    changes = []

    # ── 1. 检测新增/移除的 YAML 块（节点+组件） ──
    added_types = {}
    for m in _YAML_BLOCK_ADD_RE.finditer(diff_text):
        t = m.group(1)
        added_types[t] = added_types.get(t, 0) + 1
    removed_types = {}
    for m in _YAML_BLOCK_DEL_RE.finditer(diff_text):
        t = m.group(1)
        removed_types[t] = removed_types.get(t, 0) + 1

    # GameObject（!u!1）的新增/移除
    added_nodes = added_types.pop("1", 0)
    removed_nodes = removed_types.pop("1", 0)
    if added_nodes > 0:
        node_names = _collect_node_names(diff_text)
        if node_names:
            changes.append(f"新增 {added_nodes} 个节点：{'、'.join(sorted(node_names.keys()))}")
        else:
            changes.append(f"新增 {added_nodes} 个节点")
    if removed_nodes > 0:
        changes.append(f"移除 {removed_nodes} 个节点")

    # 其他组件的新增/移除
    for t, count in sorted(added_types.items()):
        cn = _COMPONENT_NAMES.get(t, f"组件(!u!{t})")
        changes.append(f"新增 {count} 个{cn}")
    for t, count in sorted(removed_types.items()):
        cn = _COMPONENT_NAMES.get(t, f"组件(!u!{t})")
        changes.append(f"移除 {count} 个{cn}")

    # ── 2. 检测属性变更（- m_Xxx: old / + m_Xxx: new 成对出现） ──
    prop_pairs = _OLD_NEW_PAIR_RE.findall(diff_text)
    for prop, old_val, new_val in prop_pairs:
        old_val = old_val.strip()
        new_val = new_val.strip()

        # GUID 引用字段
        if prop in _GUID_FIELDS:
            old_guid_m = _GUID_IN_TEXT_RE.search(old_val)
            new_guid_m = _GUID_IN_TEXT_RE.search(new_val)
            old_name = _resolve_guid(old_guid_m.group(1), guid_map) if old_guid_m else ""
            new_name = _resolve_guid(new_guid_m.group(1), guid_map) if new_guid_m else ""
            field_cn = _GUID_FIELDS[prop]
            if old_name and new_name and old_name != new_name:
                changes.append(f"修改 {field_cn}：从 [{old_name}] 改为 [{new_name}]")
            elif old_name and not new_name:
                changes.append(f"修改 {field_cn}：从 [{old_name}] 改为 [新资源（未匹配到本地文件）]")
            elif not old_name and new_name:
                changes.append(f"修改 {field_cn}：改为 [{new_name}]")
            else:
                changes.append(f"修改 {field_cn}：已变更")
            continue

        # 向量类型
        if prop in ("m_LocalPosition", "m_LocalRotation", "m_LocalScale"):
            old_v = _format_vec3(old_val)
            new_v = _format_vec3(new_val)
            prop_cn = _PROPERTY_NAMES.get(prop, prop)
            changes.append(f"修改 {prop_cn}：从 {old_v} 改为 {new_v}")
            continue

        # 普通属性
        prop_cn = _PROPERTY_NAMES.get(prop, prop)
        changes.append(f"修改 {prop_cn}：从 {old_val} 改为 {new_val}")

    if not changes:
        changes.append("文件无检测到的结构化变更（可能仅格式差异）")

    return changes


def _format_vec3(raw):
    """格式化 Unity 向量为可读字符串"""
    raw = raw.strip().strip("{}")
    parts = [x.strip() for x in raw.split(",")]
    return f"({', '.join(parts[:3])})"


# ═══════════════════════════════════════════════════════════
# .cs 语义解析
# ═══════════════════════════════════════════════════════════

def _parse_cs_diff(diff_text):
    """解析 .cs 文件的 diff，返回语义描述"""
    changes = []
    found_kinds = set()
    total_added = 0

    for line in diff_text.splitlines():
        m = _CS_METHOD_RE.match(line)
        if m:
            kind = m.group(2)
            name = m.group(3)
            key = f"{kind}:{name}"
            if key not in found_kinds:
                found_kinds.add(key)
                if kind == "class":
                    changes.append(f"新增类：{name}")
                elif kind == "struct":
                    changes.append(f"新增结构体：{name}")
                elif kind in ("interface", "enum"):
                    changes.append(f"新增{kind}：{name}")
                else:
                    changes.append(f"新增方法：{name}")
        if _CS_ADD_LINE_RE.match(line):
            total_added += 1

    if total_added > len(found_kinds) * 5:
        changes.append(f"新增约 {total_added} 行代码")

    if not changes:
        changes.append(f"变更约 {total_added} 行" if total_added > 0 else "微小调整")
    return changes


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def _check_semantic_in_files(file_paths):
    """从文件路径列表中判断是否存在 .prefab/.unity/.cs 文件"""
    ext_set = {".prefab", ".unity", ".cs"}
    return any(os.path.splitext(p)[1].lower() in ext_set for p in file_paths)


def _strip_repo_prefix(source_url, file_path):
    """从 SVN 仓库绝对路径中裁剪出相对 source_url 的路径"""
    url_path = urlparse(source_url).path.rstrip("/")
    url_segments = url_path.split("/")
    fp = file_path.lstrip("/")
    for i in range(len(url_segments)):
        suffix = "/".join(url_segments[i:])
        sep = "/" if suffix else ""
        if fp.startswith(suffix + sep) or fp == suffix:
            rel = fp[len(suffix) + 1:] if suffix else fp
            return rel.lstrip("/")
    return fp


def _analyze_revision_data(rev, source_url, guid_map, auth_args, file_list=None, target_path=None):
    """分析单个版本，返回结构化数据（guid_map 按需构建）"""
    result = {"rev": rev, "author": "", "date": "", "msg": "", "files": []}
    try:
        log_raw = _run_svn(
            ["log", "--xml", "-r", str(rev), source_url] + auth_args, timeout=30
        )
        import xml.etree.ElementTree as ET
        root = ET.fromstring(log_raw)
        entry = root.find(".//logentry")
        if entry is not None:
            author_el = entry.find("author")
            date_el = entry.find("date")
            msg_el = entry.find("msg")
            result["author"] = author_el.text if author_el is not None else ""
            result["date"] = date_el.text[:19] if date_el is not None and date_el.text else ""
            result["msg"] = (msg_el.text or "").strip() if msg_el is not None else ""
    except Exception:
        pass

    changed_files = file_list
    if changed_files is None:
        try:
            changed_files = _get_changed_files(source_url, rev, auth_args)
        except RuntimeError:
            return result

    for cf in changed_files:
        entry = {"path": cf["path"], "action": cf["action"], "parsed_lines": []}
        ext = os.path.splitext(cf["path"])[1].lower()
        if ext in (".prefab", ".unity", ".cs"):
            rel_path = _strip_repo_prefix(source_url, cf["path"])
            file_url = source_url.rstrip("/") + "/" + rel_path
            try:
                diff_raw = _run_svn(
                    ["diff", "-c", str(rev), file_url] + auth_args,
                    timeout=120
                )
                if diff_raw.strip():
                    if ext in (".prefab", ".unity"):
                        guids = _extract_guids_from_diff(diff_raw)
                        if guids and target_path and os.path.isdir(os.path.join(target_path, "Assets")):
                            lazy_map = _find_meta_for_guids(guids, target_path)
                        else:
                            lazy_map = {}
                        lazy_map.update(guid_map)
                        entry["parsed_lines"] = _parse_prefab_diff(diff_raw, lazy_map)
                    else:
                        entry["parsed_lines"] = _parse_cs_diff(diff_raw)
            except RuntimeError as e:
                entry["parsed_lines"] = [f"(diff 查询失败: {e})"]
        result["files"].append(entry)

    return result


def _shorten_path(source_url, file_path):
    """只保留文件名+扩展名"""
    return os.path.basename(file_path.replace("\\", "/"))


def _write_revision_to_file(f, idx, rev_data, source_url):
    """将单个版本的结构化数据写入输出文件"""
    f.write(f"{'─' * 56}\n")
    f.write(f"#{idx+1}  r{rev_data['rev']} | {rev_data['author']} | {rev_data['date']}\n")
    if rev_data["msg"]:
        f.write(f"备注：{rev_data['msg']}\n")
    f.write(f"{'─' * 56}\n")

    if not rev_data["files"]:
        f.write("  筛选后无可分析文件\n\n")
        return

    action_cn = {"A": "新增", "M": "修改", "D": "删除"}
    for fe in rev_data["files"]:
        display = _shorten_path(source_url, fe["path"])
        f.write(f"\n  [{action_cn.get(fe['action'], fe['action'])}] {display}\n")
        for line_txt in fe["parsed_lines"]:
            f.write(f"    - {line_txt}\n")
    f.write("\n")


def _split_revisions(revisions, n_workers):
    """将版本列表分片"""
    if n_workers <= 0 or not revisions:
        return [revisions] if revisions else []
    chunk_size = max(1, (len(revisions) + n_workers - 1) // n_workers)
    return [revisions[i:i + chunk_size] for i in range(0, len(revisions), chunk_size)]


_WORKER_TEMPFILES = []


def _cleanup_worker_tempfiles():
    for p in _WORKER_TEMPFILES:
        try:
            os.unlink(p)
        except Exception:
            pass
    _WORKER_TEMPFILES.clear()


def analyze_source_url(source_url, revisions, target_path,
                       version_files=None,
                       rev_file_map=None,
                       svn_user=None, svn_pass=None, log_callback=None):
    """对勾选的版本做语义分析，输出到 txt 并打开输出文件夹"""
    def _log(msg, level="info"):
        if log_callback:
            log_callback(msg, level)

    auth_args = _build_svn_auth_args(svn_user, svn_pass)
    sorted_revs = sorted(revisions, reverse=True)

    has_assets = target_path and os.path.isdir(os.path.join(target_path, "Assets"))
    if has_assets and version_files:
        if _check_semantic_in_files(version_files):
            _log("检测到语义文件，将按需查询 GUID 资源映射表")
        else:
            _log("本次分析无语义文件（.prefab/.unity/.cs），跳过 GUID 映射", "info")
    elif has_assets:
        _log("未获取到版本文件列表，跳过 GUID 映射", "warn")
    else:
        _log("未找到 Assets 目录，跳过 GUID 映射", "warn")

    output_dir = os.path.join(_script_dir, "语义分析")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"语义分析_{timestamp}.txt")

    _log(f"共 {len(sorted_revs)} 个版本待分析")

    max_workers = min(os.cpu_count() or 4, len(sorted_revs))
    chunks = _split_revisions(sorted_revs, max_workers)

    if len(chunks) <= 1:
        _log("版本数较少，单进程直接分析...")
        all_results = []
        for idx, rev in enumerate(sorted_revs):
            _log(f"正在分析 r{rev} ({idx+1}/{len(sorted_revs)})...")
            file_list = (rev_file_map or {}).get(str(rev))
            rd = _analyze_revision_data(rev, source_url, {}, auth_args, file_list=file_list, target_path=target_path)
            all_results.append(rd)
    else:
        _log(f"启动 {len(chunks)} 个子进程并行分析...")
        all_results = _run_parallel_analysis(
            chunks, source_url, {}, svn_user, svn_pass, sorted_revs, _log,
            rev_file_map=rev_file_map or {},
            target_path=target_path
        )

    with open(output_file, "w", encoding="utf-8") as f:
        _write_header(f, source_url, target_path, sorted_revs)
        for idx, rd in enumerate(all_results):
            _write_revision_to_file(f, idx, rd, source_url)

    _log(f"分析报告已保存: {output_file}")
    _log("正在打开输出文件夹...")
    try:
        os.startfile(output_dir)
    except Exception:
        _log("自动打开文件夹失败，请手动前往: " + output_dir, "warn")
    return output_file


def _run_parallel_analysis(chunks, source_url, guid_map,
                           svn_user, svn_pass, sorted_revs, _log,
                           rev_file_map=None,
                           target_path=None):
    """启动子进程并行分析，返回按 rev 排序的结果列表"""
    worker_script = os.path.join(_script_dir, "_merge_analyze_worker.py")
    auth_dict = {"svn_user": svn_user, "svn_pass": svn_pass}
    running = {}  # Popen → (arg_path, res_path, revisions_in_chunk)
    all_data = []

    for chunk in chunks:
        arg_fd, arg_path = tempfile.mkstemp(suffix=".pkl", prefix="ana_arg_")
        os.close(arg_fd)
        res_fd, res_path = tempfile.mkstemp(suffix=".pkl", prefix="ana_res_")
        os.close(res_fd)
        _WORKER_TEMPFILES.extend([arg_path, res_path])

        chunk_rfm = {str(r): rev_file_map[str(r)] for r in chunk if rev_file_map and str(r) in rev_file_map}

        worker_args = {
            "source_url": source_url,
            "revisions": chunk,
            "guid_map": guid_map,
            "auth": auth_dict,
            "rev_file_map": chunk_rfm,
            "target_path": target_path,
        }
        try:
            with open(arg_path, "wb") as f:
                pickle.dump(worker_args, f)
        except Exception:
            _cleanup_worker_tempfiles()
            raise

        proc = subprocess.Popen(
            [sys.executable, worker_script, arg_path, res_path],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        running[proc] = (arg_path, res_path, chunk)

    done = 0
    total = len(sorted_revs)
    while running:
        to_delete = []
        for proc in list(running):
            rc = proc.poll()
            if rc is None:
                continue
            arg_path, res_path, chunk_revs = running[proc]
            to_delete.append(proc)

            if rc == 0 and os.path.getsize(res_path) > 0:
                try:
                    with open(res_path, "rb") as f:
                        chunk_data = pickle.load(f)
                    all_data.extend(chunk_data)
                except Exception as e:
                    _log(f"  子进程结果读取失败: {e}", "warn")
            else:
                stderr_data = proc.stderr.read() if proc.stderr else b""
                _log(f"  子进程退出码 {rc}: {stderr_data[:200]}", "warn")

            done += len(chunk_revs)
            if done % 5 == 0 or done == total:
                _log(f"  分析进度: {done}/{total}")

        for proc in to_delete:
            del running[proc]

        if not to_delete:
            time.sleep(0.2)

    _cleanup_worker_tempfiles()
    all_data.sort(key=lambda x: x.get("rev", 0), reverse=True)
    return all_data


def _write_header(f, source_url, target_path, revisions):
    from urllib.parse import urlparse
    parsed = urlparse(source_url)
    url_path = parsed.path.strip("/")
    short_url = url_path
    for marker in ("/branches/", "/trunk", "/tags/"):
        idx = url_path.find(marker)
        if idx >= 0:
            short_url = url_path[idx+1:]
            break
    f.write("═" * 60 + "\n")
    f.write("  SVN 变更语义分析报告\n")
    f.write(f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"  源路径：{short_url}\n")
    f.write(f"  目标路径：{target_path or '（未指定）'}\n")
    f.write(f"  分析版本数：{len(revisions)}\n")
    f.write(f"  版本列表：{', '.join(f'r{r}' for r in revisions)}\n")
    f.write("═" * 60 + "\n\n")


def _get_changed_files(source_url, rev, auth_args):
    """获取单个版本的变更文件列表"""
    raw = _run_svn(
        ["diff", "--summarize", "-c", str(rev), source_url] + auth_args, timeout=60
    )
    files = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if len(line) < 3:
            continue
        action = line[0]
        path = line[2:].strip()
        files.append({"path": path, "action": action})
    return files
