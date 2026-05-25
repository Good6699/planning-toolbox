#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SVN 语义变更分析模块 — 独立于合并逻辑的纯净分析引擎"""
import hashlib
import os
import sys
import re
import subprocess
import tempfile
import pickle
import time
import yaml
import threading
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

_SCRIPT_GUID_RE = re.compile(r"guid:\s*([a-f0-9]+)")

# Unity 内置 uGUI 组件 fileID 映射（guid: f70555f144d8491a825f0804e09c671c = UnityEngine.UI.dll）
_UGUI_BUILTIN_FILEIDS = {
    1392445389: "Button",
    1980459831: "CanvasScaler",
    1741964061: "ContentSizeFitter",
    853051423: "Dropdown",
    -619905303: "EventSystem",
    383007879: "Graphic",
    1301386320: "GraphicRaycaster",
    -405508275: "HorizontalLayoutGroup",
    812294440: "HorizontalOrVerticalLayoutGroup",
    -765806418: "Image",
    575553740: "InputField",
    1679637790: "LayoutElement",
    -555945567: "LayoutGroup",
    -1200242548: "Mask",
    -1493381411: "MaskableGraphic",
    -900027084: "Outline",
    1849938685: "PositionAsUV1",
    -98529514: "RawImage",
    -146154839: "RectMask2D",
    -2061169968: "Scrollbar",
    -2041669170: "ScrollRect",
    -2095666955: "GridLayoutGroup",
    -1596909063: "Slider",
    708705254: "Text",
    -1640532299: "Toggle",
    -194418981: "VerticalLayoutGroup",
}


def _build_comp_label(comp_type, comp_name, old_block, new_block, guid_map):
    """构建组件显示标签，MonoBehaviour 尝试显示脚本名称"""
    default = _COMPONENT_NAMES.get(comp_type, comp_name)
    if comp_type != "114":
        return default
    block = old_block or new_block
    if not block:
        return default
    m_script = block.get("props", {}).get("m_Script")
    if not isinstance(m_script, dict):
        return default
    guid_str = str(m_script.get("guid", ""))
    if not guid_str:
        guid_match = _SCRIPT_GUID_RE.search(str(m_script))
        guid_str = guid_match.group(1) if guid_match else ""
    if not guid_str:
        return default
    # Unity 内置 uGUI 组件：用 fileID 查映射表
    if guid_str == "f70555f144d8491a825f0804e09c671c":
        file_id = m_script.get("fileID")
        if isinstance(file_id, int) and file_id in _UGUI_BUILTIN_FILEIDS:
            return _UGUI_BUILTIN_FILEIDS[file_id]
        return default
    # 自定义脚本：查 guid_map
    resolved = guid_map.get(guid_str, "")
    if not resolved:
        return default
    script_name = os.path.splitext(os.path.basename(resolved.replace("\\", "/")))[0]
    if script_name:
        return f"{script_name}"
    return default


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
    "m_AnchoredPosition": "锚点偏移 position",
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

# ── 输出分组标记 ──
_GRP = "\x00GRP\x00"
_DTA = "\x00DTA\x00"

# ── 正则表达式 ──
_GUID_IN_TEXT_RE = re.compile(r'guid:\s*([a-f0-9]{32})')
_CS_METHOD_RE = re.compile(r'^\+{1,3}\s+(public|private|protected|internal)\s+(void|string|int|float|bool|double|class|struct|enum|interface)\s+(\w+)')
_CS_ADD_LINE_RE = re.compile(r'^\+[^+]')


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


def _build_full_guid_map(target_path):
    """一次性遍历 Assets/ 构建完整 {guid: asset_relative_path} 映射"""
    assets_dir = os.path.join(target_path, "Assets")
    if not os.path.isdir(assets_dir):
        return {}
    result = {}
    for root, dirs, files in os.walk(assets_dir):
        dirs[:] = [d for d in dirs if d not in ("Library", "Temp", "obj", "Obj", "Plugin", "Plugins")]
        for fname in files:
            if not fname.endswith(".meta"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    head = fh.read(200)
                m = re.search(r'guid:\s*([a-f0-9]+)', head)
                if m:
                    guid = m.group(1)
                    asset_rel = os.path.relpath(fpath[:-5], target_path).replace("\\", "/")
                    result[guid] = asset_rel
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
# Unity YAML 解析（使用 PyYAML）
# ═══════════════════════════════════════════════════════════

_YAML_DOC_RE = re.compile(r'^--- !u!(\d+) &(\d+)', re.MULTILINE)


def _preprocess_unity_yaml(text):
    """预处理 Unity YAML：去掉 %TAG 指令和 !u! 标签，使 PyYAML 可解析"""
    lines = text.splitlines()
    result = []
    for line in lines:
        # 跳过 %YAML, %TAG 指令行
        if line.startswith("%YAML") or line.startswith("%TAG"):
            continue
        # 替换行内的 !u!N 标签
        line = re.sub(r'!u!\d+\s*', '', line)
        result.append(line)
    return "\n".join(result)


def _extract_file_id(orig_doc, doc_text):
    """从 YAML 文档头中提取 (comp_type, file_id)，支持多种格式"""
    m = _YAML_DOC_RE.match(orig_doc) or _YAML_DOC_RE.search(orig_doc)
    if m:
        return m.group(1), m.group(2)
    m2 = re.search(r'!u!(\d+)\s+&(\d+)', orig_doc)
    if m2:
        return m2.group(1), m2.group(2)
    m3 = re.search(r'&(\d+)', doc_text)
    if m3:
        return "", m3.group(1)
    return None, None


def _unify_yaml_doc(doc_text):
    """确保 YAML 文档以 --- 开头"""
    if not doc_text.startswith("---"):
        return "--- " + doc_text
    return doc_text


def _parse_unity_yaml(text, target_file_ids=None):
    """解析 Unity .prefab/.unity 为 {fileID: {type, node_name, component, props}}

    如果指定 target_file_ids，只解析这些 fileID 的块（大幅加速）
    使用 CSafeLoader（C 实现，比 SafeLoader 快 5-10 倍）
    """
    if not text or not text.strip():
        return {}
    # 预处理前去匹配 fileID 和组件类型
    # 移除 %YAML/%TAG 头行
    orig_lines = [ln for ln in text.splitlines() if not ln.startswith("%YAML") and not ln.startswith("%TAG")]
    orig_clean = "\n".join(orig_lines)
    orig_docs = orig_clean.strip().split("\n--- ")
    # 预处理去掉 Unity 自定义标签
    processed_text = _preprocess_unity_yaml(text)
    blocks = {}
    docs = processed_text.strip().split("\n--- ")
    for i, doc in enumerate(docs):
        doc = doc.strip()
        if not doc:
            continue

        # 从原始文本提取 fileID（在 YAML 解析前判断是否跳过）
        orig_doc = orig_docs[i] if i < len(orig_docs) else ""
        comp_type, file_id = _extract_file_id(orig_doc, doc)
        if file_id is None:
            continue

        # 如果指定了目标 fileID 且不在其中，跳过（核心加速）
        if target_file_ids is not None and file_id not in target_file_ids:
            continue

        try:
            full_text = _unify_yaml_doc(doc)
            data = yaml.load(full_text, Loader=yaml.CSafeLoader)
            if not isinstance(data, dict):
                continue
        except Exception:
            try:
                data = yaml.safe_load(full_text)
                if not isinstance(data, dict):
                    continue
            except yaml.YAMLError:
                continue

        node_name = ""
        component = ""
        props = data if isinstance(data, dict) else {}
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            component = k
            props = v
            if comp_type == "1" and "m_Name" in v:
                node_name = str(v["m_Name"]) if v["m_Name"] is not None else ""
            break

        blocks[file_id] = {
            "type": comp_type,
            "fileID": file_id,
            "component": component,
            "node_name": node_name,
            "props": props,
        }
    return blocks


def _walk_hierarchy(go_fid, go_names, go_to_tf, tf_to_go, blocks):
    """Walk up Transform.m_Father chain to build a /-separated hierarchy path"""
    path_parts = []
    current_go_fid = go_fid
    visited = set()
    while current_go_fid and current_go_fid not in visited:
        visited.add(current_go_fid)
        name = go_names.get(current_go_fid, "")
        path_parts.insert(0, name or f"节点({current_go_fid})")
        tf_fid = go_to_tf.get(current_go_fid)
        if tf_fid and tf_fid in blocks:
            tf_block = blocks[tf_fid]
            father_ref = tf_block.get("props", {}).get("m_Father")
            if isinstance(father_ref, dict) and "fileID" in father_ref:
                parent_tf_fid = str(father_ref["fileID"])
                if parent_tf_fid == "0":
                    break
                parent_go_fid = tf_to_go.get(parent_tf_fid)
                if parent_go_fid:
                    current_go_fid = parent_go_fid
                else:
                    break
            else:
                break
        else:
            break
    return "/".join(path_parts)


def _build_prefab_index(blocks):
    """Build lookup tables from a Unity prefab block dict:

    Returns (go_names, go_to_tf, tf_to_go, comp_to_go)
    """
    go_names = {}
    go_to_tf = {}
    tf_to_go = {}
    comp_to_go = {}
    for bid, b in blocks.items():
        props = b.get("props", {})
        if b["type"] == "1":
            go_names[bid] = props.get("m_Name", "") or ""
            comp_list = props.get("m_Component")
            if isinstance(comp_list, list):
                for item in comp_list:
                    if isinstance(item, dict):
                        cid = None
                        sub = item.get("component")
                        if isinstance(sub, dict) and "fileID" in sub:
                            cid = str(sub["fileID"])
                        elif "fileID" in item:
                            cid = str(item["fileID"])
                        if cid:
                            comp_to_go[cid] = bid
        go_ref = props.get("m_GameObject")
        if isinstance(go_ref, dict) and "fileID" in go_ref:
            go_id = str(go_ref["fileID"])
            if b["type"] in ("4", "224"):
                go_to_tf[go_id] = bid
                tf_to_go[bid] = go_id
    return go_names, go_to_tf, tf_to_go, comp_to_go


def _find_go_for_block(fid, block, comp_to_go):
    """Find which GameObject a block belongs to.

    Returns go_fid string or None.
    """
    if block["type"] == "1":
        return str(fid)
    sfid = str(fid)
    if sfid in comp_to_go:
        return comp_to_go[sfid]
    go_ref = block.get("props", {}).get("m_GameObject")
    if isinstance(go_ref, dict) and "fileID" in go_ref and str(go_ref["fileID"]) != "0":
        return str(go_ref["fileID"])
    return None


def _build_node_path(fid, blocks):
    """Build full hierarchy path like 'Canvas/Panel/Button' for a block fileID"""
    block = blocks.get(str(fid))
    if not block:
        return ""

    go_names, go_to_tf, tf_to_go, comp_to_go = _build_prefab_index(blocks)
    go_fid = _find_go_for_block(fid, block, comp_to_go)

    if not go_fid:
        name = go_names.get(str(fid), "")
        return name or f"节点({fid})"

    return _walk_hierarchy(go_fid, go_names, go_to_tf, tf_to_go, blocks)


def _compare_prefab_trees(old_blocks, new_blocks, guid_map):
    """对比两个版本的 prefab 结构树，返回人类可读的变更列表"""
    structured = _compare_prefab_trees_structured(old_blocks, new_blocks, guid_map)
    return _format_structured_diffs(structured)


def _compare_prefab_trees_structured(old_blocks, new_blocks, guid_map):
    """对比两个版本的 prefab 结构树，返回结构化变更列表

    返回 list[dict]：
    {hierarchy_path, comp_label, fileID, prop_key, sub_lines}
    """
    all_ids = set(old_blocks.keys()) | set(new_blocks.keys())
    result = []

    # 构建 fileID → 组件名 映射表（一次性，用于 m_Component 列表显示）
    merged_blocks = {}
    merged_blocks.update(old_blocks)
    merged_blocks.update(new_blocks)
    fileid_label_map = {}
    for bfid, b in merged_blocks.items():
        fileid_label_map[bfid] = _build_comp_label(b.get("type", ""), b.get("component", ""), b, b, guid_map)

    for fid in all_ids:
        old = old_blocks.get(fid)
        new = new_blocks.get(fid)
        old_type = old["type"] if old else (new["type"] if new else "")
        comp_name = old["component"] if old else (new["component"] if new else "")

        hierarchy_path = _build_node_path(fid, merged_blocks)
        comp_label = _build_comp_label(old_type, comp_name, old, new, guid_map)

        if old and not new:
            result.append({
                "hierarchy_path": hierarchy_path,
                "comp_label": comp_label,
                "fileID": fid,
                "prop_key": "__node__",
                "sub_lines": ["移除节点" if old_type == "1" else f"移除了 {comp_label}"],
            })
            continue

        if new and not old:
            result.append({
                "hierarchy_path": hierarchy_path,
                "comp_label": comp_label,
                "fileID": fid,
                "prop_key": "__node__",
                "sub_lines": ["新增节点" if new["type"] == "1" else f"新增了 {comp_label}"],
            })
            continue

        old_props = old["props"]
        new_props = new["props"]
        prop_diffs = _compare_props_structured(old_props, new_props, guid_map, fileid_label_map=fileid_label_map)
        for pd in prop_diffs:
            pd["hierarchy_path"] = hierarchy_path
            pd["comp_label"] = comp_label
            pd["fileID"] = fid
            result.append(pd)

    return result


def _format_structured_diffs(structured_list):
    """将结构化 diff 列表按 Unity 节点路径分组，合并同类项"""
    groups = {}
    group_order = []
    for item in structured_list:
        hp = item["hierarchy_path"]
        if hp not in groups:
            groups[hp] = []
            group_order.append(hp)
        groups[hp].append(item)

    def _extract_m_comp_info(sub_lines):
        """从 m_Component sub_lines 提取新增/删除组件名和数量字符串"""
        added = set()
        removed = set()
        count = ""
        for s in sub_lines:
            st = s.strip()
            if st.startswith("+ ") and not st.startswith("+ ("):
                added.add(st[2:])
            elif st.startswith("- ") and not st.startswith("- ("):
                removed.add(st[2:])
            elif st.startswith("(共"):
                count = st
        return added, removed, count

    result = []
    for hp in group_order:
        items = groups[hp]
        m_comp_added, m_comp_removed, m_comp_count = set(), set(), ""
        have_m_comp = False
        for item in items:
            if item.get("prop_key") == "m_Component":
                have_m_comp = True
                a, r, c = _extract_m_comp_info(item.get("sub_lines", []))
                m_comp_added |= a
                m_comp_removed |= r
                if c:
                    m_comp_count = c

        # 从 m_Component 生成摘要行
        m_comp_lines = []
        if have_m_comp:
            for name in sorted(m_comp_added):
                line = f"+ 新增插件: {name}"
                if m_comp_count:
                    line += f" {m_comp_count}"
                m_comp_lines.append(line)
            for name in sorted(m_comp_removed):
                line = f"- 移除插件: {name}"
                m_comp_lines.append(line)

        # 收集其他变更行，过滤被 m_Component 覆盖的 __node__
        other_lines = []
        for item in items:
            if item.get("prop_key") == "m_Component":
                continue
            cl = item.get("comp_label", "")
            subs = item.get("sub_lines") or []
            if not subs:
                continue
            if have_m_comp and cl in m_comp_added | m_comp_removed:
                continue
            # sub_lines[0] 是摘要行（如"修改了 锚点最大值"），后续行是旧值/新值
            for s in subs:
                other_lines.append(s)

        node_lines = m_comp_lines + other_lines
        if not node_lines:
            continue

        result.append("")
        result.append(f"{_GRP}{hp}:")
        for s in node_lines:
            result.append(f"{_DTA}  {s}")

    return result


def _build_diff_label(item):
    """构建 diff 条目的一行标签，对 m_Component 做 flatten 处理"""
    hp = item["hierarchy_path"]
    cl = item["comp_label"]
    subs = item.get("sub_lines", [])

    if cl == "GameObject/节点":
        if item["prop_key"] == "m_Component" and subs:
            start = 0
            if subs[0].startswith("修改了"):
                start = 1
            rest = subs[start:]
            if rest:
                summary = " ".join(r.strip() for r in rest)
                return f"{hp} → {summary}"
        return hp
    return f"{hp} → {cl}"


def _compare_props_structured(old_props, new_props, guid_map, fileid_label_map=None):
    """对比两个 props dict，返回结构化变更列表"""
    changes = []
    all_keys = set(old_props.keys()) | set(new_props.keys())

    for key in all_keys:
        old_val = old_props.get(key)
        new_val = new_props.get(key)
        raw = None

        if key not in new_props:
            raw = _format_prop_change(key, old_val, "", guid_map, deleted=True, fileid_label_map=fileid_label_map)
            if raw:
                changes.append({"prop_key": key, "sub_lines": raw.split("\n")})
            continue

        if key not in old_props:
            raw = _format_prop_change(key, "", new_val, guid_map, added=True, fileid_label_map=fileid_label_map)
            if raw:
                changes.append({"prop_key": key, "sub_lines": raw.split("\n")})
            continue

        if old_val == new_val:
            continue

        if isinstance(old_val, dict) and isinstance(new_val, dict):
            # 如果是 fileID 引用（如 m_Father），保留 dict 结构让 _format_prop_change 解析
            if "fileID" in old_val or "fileID" in new_val:
                raw = _format_prop_change(key, old_val, new_val, guid_map, fileid_label_map=fileid_label_map) if old_val != new_val else None
            else:
                raw = _format_prop_change(key, str(old_val), str(new_val), guid_map, fileid_label_map=fileid_label_map) if old_val != new_val else None
        elif isinstance(old_val, list) and isinstance(new_val, list):
            raw = _format_list_diff(key, old_val, new_val, guid_map, fileid_label_map=fileid_label_map)
        else:
            ov = str(old_val) if old_val is not None else ""
            nv = str(new_val) if new_val is not None else ""
            raw = _format_prop_change(key, ov, nv, guid_map, fileid_label_map=fileid_label_map)
        if raw:
            changes.append({"prop_key": key, "sub_lines": raw.split("\n")})

    return changes


def _list_summary(lst):
    """生成列表的简短摘要，每项单独一行"""
    if not lst:
        return "[]"
    if len(lst) == 1:
        return f"[{lst[0]}]"
    lines = ["["]
    for item in lst[:5]:
        lines.append(f"        {item},")
    if len(lst) > 5:
        lines.append(f"        ...({len(lst)}项)")
    lines.append("]")
    return "\n".join(lines)


def _resolve_list_item_label(item, fileid_label_map):
    """从列表项 dict 中提取 fileID 并解析为组件名，失败返回 None"""
    if not isinstance(item, dict) or not fileid_label_map:
        return None
    for v in item.values():
        if isinstance(v, dict) and "fileID" in v:
            fid = str(v["fileID"])
            label = fileid_label_map.get(fid)
            if label:
                return label
    return None


def _get_dict_item_key(item):
    """从 dict 类型的列表项中提取标识键（m_key、fileID、guid 等），用于按身份匹配"""
    if not isinstance(item, dict):
        return None
    for k in ("m_key",):
        if k in item:
            return str(item[k])
    for v in item.values():
        if isinstance(v, dict) and "fileID" in v:
            return f"fid:{v['fileID']}"
    return None


def _format_list_diff(key, old_list, new_list, guid_map, fileid_label_map=None):
    """对比两个列表，只输出差异部分（新增/删除/修改项），跳过相同的项"""
    prop_cn = _PROPERTY_NAMES.get(key, key)

    def _item_str(item):
        """将列表项转为可读字符串，尝试解析 fileID"""
        label = _resolve_list_item_label(item, fileid_label_map) if fileid_label_map else None
        return label or str(item)

    # 尝试按身份键匹配（对 dict 类型列表项，如 m_vfxList 有 m_key）
    old_keys = {}
    new_keys = {}
    is_dict_list = bool(old_list and isinstance(old_list[0], dict))

    if is_dict_list:
        for idx, item in enumerate(old_list):
            k = _get_dict_item_key(item)
            if k:
                old_keys[k] = idx
        for idx, item in enumerate(new_list):
            k = _get_dict_item_key(item)
            if k:
                new_keys[k] = idx

    if old_keys and new_keys:
        # 按键匹配：存在双方 → 比较是否真变化
        changed_items = []
        truly_removed = []
        truly_added = []
        matched_new = set()
        matched_old = set()

        for old_key, old_idx in old_keys.items():
            if old_key in new_keys:
                matched_old.add(old_idx)
                matched_new.add(new_keys[old_key])
                old_s = _item_str(old_list[old_idx])
                new_s = _item_str(new_list[new_keys[old_key]])
                if old_s != new_s:
                    changed_items.append(old_key)
            else:
                truly_removed.append(_item_str(old_list[old_idx]))

        for new_idx in range(len(new_list)):
            if new_idx not in matched_new:
                truly_added.append(_item_str(new_list[new_idx]))

        if not truly_removed and not truly_added and not changed_items:
            return None

        lines = [f"修改了 {prop_cn}"]
        if truly_removed:
            lines.append(f"      移除了 {len(truly_removed)} 项:")
            for r in truly_removed:
                lines.append(f"        - {r}")
        if truly_added:
            lines.append(f"      新增了 {len(truly_added)} 项:")
            for a in truly_added:
                lines.append(f"        + {a}")
        if changed_items:
            lines.append(f"      修改了 {len(changed_items)} 项:")
            for c in changed_items:
                lines.append(f"        ~ {c}")
        return "\n".join(lines)

    # 无身份键可匹配，回退到旧逻辑（全量字符串比较）
    old_strs = [_item_str(item) for item in old_list]
    new_strs = [_item_str(item) for item in new_list]
    old_set = set(old_strs)
    new_set = set(new_strs)

    removed = [s for s in old_strs if s not in new_set]
    added = [s for s in new_strs if s not in old_set]

    if not removed and not added:
        return None

    lines = [f"修改了 {prop_cn}"]
    if removed:
        lines.append(f"      移除了 {len(removed)} 项:")
        for r in removed:
            lines.append(f"        - {r}")
    if added:
        lines.append(f"      新增了 {len(added)} 项:")
        for a in added:
            lines.append(f"        + {a}")
    total_old = len(old_list)
    total_new = len(new_list)
    if total_old != total_new:
        lines.append(f"      (共 {total_old} → {total_new} 项)")
    return "\n".join(lines)


def _format_prop_change(prop, old_val, new_val, guid_map, deleted=False, added=False, fileid_label_map=None):
    """格式化单个属性变更为中文描述"""
    prop_cn = _PROPERTY_NAMES.get(prop, prop)

    # 解析 fileID 引用（如 m_Father 的 {'fileID': xxx}）
    def _fileid_to_name(val):
        if isinstance(val, dict) and "fileID" in val and fileid_label_map:
            fid = str(val["fileID"])
            return fileid_label_map.get(fid) or val
        return val

    if prop in _GUID_FIELDS:
        field_cn = _GUID_FIELDS[prop]
        if deleted:
            return f"移除了 {field_cn}\n      旧值: [{old_val}]"
        if added:
            new_guid_m = _GUID_IN_TEXT_RE.search(new_val)
            new_name = _resolve_guid(new_guid_m.group(1), guid_map) if new_guid_m else ""
            if new_name:
                return f"新增了 {field_cn}\n      新值: [{new_name}]"
            return f"新增了 {field_cn}"
        old_guid_m = _GUID_IN_TEXT_RE.search(old_val)
        new_guid_m = _GUID_IN_TEXT_RE.search(new_val)
        old_name = _resolve_guid(old_guid_m.group(1), guid_map) if old_guid_m else ""
        new_name = _resolve_guid(new_guid_m.group(1), guid_map) if new_guid_m else ""
        if old_name and new_name and old_name != new_name:
            return f"修改了 {field_cn}\n      旧值: [{old_name}]\n      新值: [{new_name}]"
        elif new_name:
            return f"修改了 {field_cn}\n      新值: [{new_name}]"
        return f"修改了 {field_cn}（已变更）"

    if prop in ("m_LocalPosition", "m_LocalRotation", "m_LocalScale"):
        if deleted:
            return f"移除了 {prop_cn}\n      旧值: {_format_vec3(old_val)}"
        if added:
            return f"新增了 {prop_cn}\n      新值: {_format_vec3(new_val)}"
        old_v = _format_vec3(old_val)
        new_v = _format_vec3(new_val)
        return f"修改了 {prop_cn}\n      旧值: {old_v}\n      新值: {new_v}"

    if deleted:
        ov = _fileid_to_name(old_val)
        if ov and ov != "{}":
            return f"移除了 {prop_cn}\n      旧值: {ov}"
        return f"移除了 {prop_cn}"
    if added:
        nv = _fileid_to_name(new_val)
        if nv and nv != "{}":
            return f"新增了 {prop_cn}\n      新值: {nv}"
        return f"新增了 {prop_cn}"

    if old_val == new_val:
        return None
    ov = _fileid_to_name(old_val)
    nv = _fileid_to_name(new_val)
    return f"修改了 {prop_cn}\n      旧值: {ov}\n      新值: {nv}"


def _format_vec3(raw):
    """格式化 Unity 向量为可读字符串"""
    if isinstance(raw, dict):
        x = raw.get("x", "")
        y = raw.get("y", "")
        z = raw.get("z", "")
        return f"({x}, {y}, {z})"
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


_RAW_BLOCK_RE = re.compile(
    r'^--- !u!(\d+) &(\d+).*?\n(?=(?:--- !u!|\Z))',
    re.MULTILINE | re.DOTALL
)


def _extract_raw_blocks(text):
    """Split Unity YAML text into {fileID: raw_block_text} by --- !u! markers"""
    blocks = {}
    for m in _RAW_BLOCK_RE.finditer(text):
        comp_type = m.group(1)
        file_id = m.group(2)
        blocks[file_id] = {"raw": m.group(0), "type": comp_type}
    return blocks


def _detect_changed_blocks(old_raw, new_raw, _log=None):
    """Compare raw block hashes to find which fileIDs changed between two versions.

    Returns (all_ids, changed_ids, changed_count_log)
    """
    all_ids = set(old_raw.keys()) | set(new_raw.keys())
    changed_ids = set()
    for fid in all_ids:
        if fid not in old_raw or fid not in new_raw:
            changed_ids.add(fid)
        else:
            old_md5 = hashlib.md5(old_raw[fid]["raw"].encode("utf-8")).hexdigest()
            new_md5 = hashlib.md5(new_raw[fid]["raw"].encode("utf-8")).hexdigest()
            if old_md5 != new_md5:
                changed_ids.add(fid)

    if _log and changed_ids:
        _log(f"    变化块 fileID: {', '.join(sorted(changed_ids, key=int)[:10])}{'...' if len(changed_ids) > 10 else ''}")
    return all_ids, changed_ids


def _collect_parse_ids(all_ids, changed_ids, old_raw, new_raw):
    """Determine which blocks need YAML parsing: changed blocks + GameObjects + Transforms (for hierarchy)"""
    parse_old_ids = set()
    parse_new_ids = set()
    for fid in all_ids:
        b_old = old_raw.get(fid)
        b_new = new_raw.get(fid)
        btype = (b_old or b_new)["type"]
        # Always parse: changes + GameObjects + Transforms (hierarchy needed for paths)
        if fid in changed_ids or btype in ("1", "4", "224"):
            if fid in old_raw:
                parse_old_ids.add(fid)
            if fid in new_raw:
                parse_new_ids.add(fid)
    return parse_old_ids, parse_new_ids


def _parse_unity_yaml_blocks(text, file_ids):
    """解析 YAML 文本中指定 fileID 的块，返回 {fileID: {type, node_name, component, props}}"""
    if not text or not text.strip() or not file_ids:
        return {}
    full = _parse_unity_yaml(text, target_file_ids=file_ids)
    result = {}
    for fid in file_ids:
        if fid in full:
            result[fid] = full[fid]
    return result


def _compare_prefab_texts_fast(old_text, new_text, guid_map, _log=None):
    """对比两个版本的 prefab 文本，只 YAML 解析有变化的块以加速"""
    old_raw = _extract_raw_blocks(old_text)
    new_raw = _extract_raw_blocks(new_text)
    all_ids, changed_ids = _detect_changed_blocks(old_raw, new_raw, _log=_log)

    if _log:
        total = len(all_ids)
        changed = len(changed_ids)
        _log(f"    总 {total} 个块，{changed} 个有变化，跳过 {total - changed} 个")

    parse_old_ids, parse_new_ids = _collect_parse_ids(all_ids, changed_ids, old_raw, new_raw)

    old_parsed = _parse_unity_yaml_blocks(old_text, parse_old_ids)
    new_parsed = _parse_unity_yaml_blocks(new_text, parse_new_ids)

    return _compare_prefab_trees(old_parsed, new_parsed, guid_map)


def _build_rev_file_map(sorted_revs, rev_file_map, source_url, auth_args):
    """筛选出选中版本中的语义文件列表"""
    result = {}
    for rev in sorted_revs:
        file_list = (rev_file_map or {}).get(str(rev))
        if file_list is None:
            try:
                file_list = _get_changed_files(source_url, rev, auth_args)
            except RuntimeError:
                continue
        semantic = [cf for cf in file_list if os.path.splitext(cf["path"])[1].lower() in (".prefab", ".unity", ".cs")]
        if semantic:
            result[str(rev)] = semantic
    return result


def _run_parallel_squash_revs(rev_chunks, source_url, rev_file_map, svn_user, svn_pass, target_path, _log, guid_map=None):
    """启动子进程并行分析，返回所有 entries

    结构对齐 _run_parallel_analysis 的成熟模式
    """
    worker_script = os.path.join(_script_dir, "_squash_worker.py")
    auth_dict = {"svn_user": svn_user, "svn_pass": svn_pass}
    running = {}
    stderr_threads = {}
    all_entries = []

    # 使用父进程预构建的 GUID 映射（如有），否则自建一次（所有 worker 共享）
    full_guid_map = guid_map if guid_map else (_build_full_guid_map(target_path) if target_path else {})
    if _log and full_guid_map:
        _log(f"  预构建 GUID 映射完成: {len(full_guid_map)} 项")

    for chunk in rev_chunks:
        arg_fd, arg_path = tempfile.mkstemp(suffix=".pkl", prefix="sq_arg_")
        os.close(arg_fd)
        res_fd, res_path = tempfile.mkstemp(suffix=".pkl", prefix="sq_res_")
        os.close(res_fd)
        _WORKER_TEMPFILES.extend([arg_path, res_path])

        chunk_rfm = {str(r): rev_file_map.get(str(r), []) for r in chunk}

        worker_args = {
            "source_url": source_url,
            "revisions": chunk,
            "rev_file_map": chunk_rfm,
            "auth": auth_dict,
            "target_path": target_path,
            "guid_map": full_guid_map,
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
        t = threading.Thread(target=_pipe_stderr_to_log, args=(proc, _log), daemon=True)
        t.start()
        stderr_threads[proc] = t

    while running:
        finished = []
        for proc in list(running):
            rc = proc.poll()
            if rc is None:
                continue
            arg_path, res_path, chunk_revs = running[proc]
            finished.append(proc)

            stderr_threads[proc].join(timeout=2)

            if rc == 0 and os.path.getsize(res_path) > 0:
                try:
                    with open(res_path, "rb") as f:
                        entries = pickle.load(f)
                        if entries:
                            all_entries.extend(entries)
                except Exception as e:
                    if _log:
                        _log(f"  子进程结果读取失败: {e}", "warn")

            # 立即删除临时文件
            for p in (arg_path, res_path):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                        _WORKER_TEMPFILES.remove(p)
                except (ValueError, OSError):
                    pass

        for proc in finished:
            del running[proc]
            del stderr_threads[proc]

        if not finished:
            time.sleep(0.2)

    return all_entries


def _pipe_stderr_to_log(proc, _log):
    """线程函数：逐行读取子进程 stderr 并实时输出"""
    if not _log or not proc.stderr:
        return
    # Windows 中文环境下子进程 stderr 可能为 GBK，先试 UTF-8 再回退
    _sys_enc = "gbk" if os.name == "nt" else "utf-8"
    try:
        for line in iter(proc.stderr.readline, b""):
            try:
                text = line.decode("utf-8").rstrip()
            except UnicodeDecodeError:
                text = line.decode(_sys_enc, errors="replace").rstrip()
            if text:
                _log(text)
        proc.stderr.close()
    except Exception:
        pass


def _analyze_single_rev_prefabs(rev, file_list, source_url, auth_args, target_path, _log):
    """分析单个版本中所有 .prefab/.unity 文件，返回 entries"""
    entries = []
    prv_rev = max(1, rev - 1)
    for cf in [cf for cf in file_list if os.path.splitext(cf["path"])[1].lower() in (".prefab", ".unity")]:
        rel_path = _strip_repo_prefix(source_url, cf["path"])
        file_url = source_url.rstrip("/") + "/" + rel_path
        fname = os.path.basename(cf["path"])
        _t0 = time.time()
        try:
            old_text = _run_svn(["cat", "-r", str(prv_rev), file_url] + auth_args, timeout=120)
        except RuntimeError:
            old_text = ""
        if _log:
            _log(f"  r{rev} {fname}: 旧版 svn cat 耗时 {time.time()-_t0:.1f}s")
        _t0 = time.time()
        try:
            new_text = _run_svn(["cat", "-r", str(rev), file_url] + auth_args, timeout=120)
        except RuntimeError:
            new_text = ""
        if _log:
            _log(f"  r{rev} {fname}: 新版 svn cat 耗时 {time.time()-_t0:.1f}s")
        _t0 = time.time()
        all_guids = _extract_guids_from_diff(old_text + new_text)
        lazy_map = {}
        if all_guids and target_path and os.path.isdir(os.path.join(target_path, "Assets")):
            lazy_map = _find_meta_for_guids(all_guids, target_path)
        if _log:
            _log(f"  r{rev} {fname}: GUID 映射耗时 {time.time()-_t0:.1f}s (guid={len(all_guids)}, found={len(lazy_map)})")
        _t0 = time.time()
        parsed = _compare_prefab_texts_fast(old_text, new_text, lazy_map, _log=_log)
        if _log:
            _log(f"  r{rev} {fname}: YAML 对比耗时 {time.time()-_t0:.1f}s ({len(parsed)} 条变更)")
        if parsed:
            entries.append({"path": cf["path"], "action": "M", "parsed_lines": parsed})
    return entries


def _analyze_squash_revisions(sorted_revs, source_url, guid_map, auth_args, rev_file_map, target_path, _log=None, svn_user=None, svn_pass=None):
    """对多个版本做汇总分析：按版本分片并行 → 文件路径合并（最新覆盖）

    流程：
    1. 构建 {rev: [语义文件列表]}
    2. 按版本分片，各片并行分析（子进程）
    3. 每个子进程内：逐版本分析 (rev-1 → rev) 直接输出已格式化的 parsed_lines
    4. 主进程按文件路径合并，后写入的（新版本）覆盖先写入的（旧版本）
    5. .cs 文件单独处理
    """
    min_rev = min(sorted_revs)
    max_rev = max(sorted_revs)

    if _log:
        _log(f"汇总模式：{len(sorted_revs)} 个版本 (r{min_rev} → r{max_rev})，按版本并行分析")

    rev_file_map_filtered = _build_rev_file_map(sorted_revs, rev_file_map, source_url, auth_args)

    result = {
        "rev": f"{min_rev}-{max_rev}",
        "author": "",
        "date": "",
        "msg": f"汇总 {len(sorted_revs)} 个版本 (r{min_rev} → r{max_rev}) 的变更",
        "files": [],
        "_squash": True,
    }

    n_revs = len(sorted_revs)
    if n_revs == 1:
        all_entries = []
        for rev in sorted_revs:
            file_list = rev_file_map_filtered.get(str(rev), [])
            all_entries.extend(_analyze_single_rev_prefabs(rev, file_list, source_url, auth_args, target_path, _log))
    else:
        max_workers = min(n_revs, os.cpu_count() or 4)
        rev_chunks = _split_revisions(sorted_revs, max_workers)
        if _log:
            _log(f"  按 {len(rev_chunks)} 个分片并行分析 {n_revs} 个版本...")
        all_entries = _run_parallel_squash_revs(rev_chunks, source_url, rev_file_map_filtered, svn_user, svn_pass, target_path, _log, guid_map=guid_map)

    # 按文件路径合并（后写入 = 新版本 覆盖旧版本）
    path_map = {}
    for entry in all_entries:
        path_map[entry["path"]] = entry

    # .cs 文件单独处理
    cs_handled = set()
    for rev in sorted_revs:
        file_list = rev_file_map_filtered.get(str(rev), [])
        for cf in file_list:
            if cf["path"] in cs_handled:
                continue
            if os.path.splitext(cf["path"])[1].lower() != ".cs":
                continue
            cs_handled.add(cf["path"])
            rel_path = _strip_repo_prefix(source_url, cf["path"])
            file_url = source_url.rstrip("/") + "/" + rel_path
            try:
                diff_raw = _run_svn(["diff", "-c", str(max_rev), file_url] + auth_args, timeout=120)
                entry = {"path": cf["path"], "action": "M", "parsed_lines": []}
                if diff_raw.strip():
                    entry["parsed_lines"] = _parse_cs_diff(diff_raw)
                path_map[cf["path"]] = entry
            except RuntimeError as e:
                path_map[cf["path"]] = {"path": cf["path"], "action": "M", "parsed_lines": [f"(分析失败: {e})"]}

    result["files"] = list(path_map.values())
    return result


def _analyze_prefab_file(cf, source_url, rev, auth_args, guid_map, target_path, _log=None):
    """分析 .prefab/.unity 文件的语义变更（下载旧版+新版，YAML 树对比）"""
    rel_path = _strip_repo_prefix(source_url, cf["path"])
    file_url = source_url.rstrip("/") + "/" + rel_path
    fname = os.path.basename(cf["path"])

    prv_rev = max(1, rev - 1)
    _t0 = time.time()
    try:
        old_text = _run_svn(["cat", "-r", str(prv_rev), file_url] + auth_args, timeout=120)
    except RuntimeError:
        old_text = ""
    if _log:
        _log(f"  r{rev} {fname}: 旧版 svn cat 耗时 {time.time()-_t0:.1f}s ({'成功' if old_text else '失败'})")

    _t0 = time.time()
    try:
        new_text = _run_svn(["cat", "-r", str(rev), file_url] + auth_args, timeout=120)
    except RuntimeError:
        new_text = ""
    if _log:
        _log(f"  r{rev} {fname}: 新版 svn cat 耗时 {time.time()-_t0:.1f}s ({'成功' if new_text else '失败'})")

    _t0 = time.time()
    all_guids = _extract_guids_from_diff(old_text + new_text)
    lazy_map = {}
    if guid_map:
        for g in all_guids:
            if g in guid_map:
                lazy_map[g] = guid_map[g]
    elif all_guids and target_path and os.path.isdir(os.path.join(target_path, "Assets")):
        lazy_map = _find_meta_for_guids(all_guids, target_path)
    lazy_map.update(guid_map)
    if _log:
        _log(f"  r{rev} {fname}: GUID 映射耗时 {time.time()-_t0:.1f}s (guid={len(all_guids)}, found={len(lazy_map)})")

    _t0 = time.time()
    result = _compare_prefab_texts_fast(old_text, new_text, lazy_map, _log=_log)
    if _log:
        _log(f"  r{rev} {fname}: YAML 对比耗时 {time.time()-_t0:.1f}s ({len(result)} 条变更)")
    return result


def _analyze_revision_data(rev, source_url, guid_map, auth_args, file_list=None, target_path=None, _log=None):
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
                if ext in (".prefab", ".unity"):
                    if _log:
                        _log(f"  r{rev}: 分析 {os.path.basename(cf['path'])}...")
                    entry["parsed_lines"] = _analyze_prefab_file(cf, source_url, rev, auth_args, guid_map, target_path, _log=_log)
                else:
                    diff_raw = _run_svn(
                        ["diff", "-c", str(rev), file_url] + auth_args,
                        timeout=120
                    )
                    if diff_raw.strip():
                        entry["parsed_lines"] = _parse_cs_diff(diff_raw)
            except RuntimeError as e:
                entry["parsed_lines"] = [f"(分析失败: {e})"]
        result["files"].append(entry)

    return result


def _shorten_path(source_url, file_path):
    """只保留文件名+扩展名"""
    return os.path.basename(file_path.replace("\\", "/"))


def _write_revision_to_file(f, idx, rev_data, source_url):
    """将单个版本的结构化数据写入输出文件"""
    is_squash = rev_data.get("_squash", False)

    if is_squash:
        f.write(f"{'─' * 56}\n")
        f.write(f"  {rev_data['msg']}\n")
        f.write(f"{'─' * 56}\n")
    else:
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
            if not line_txt:
                f.write("\n")
            elif line_txt.startswith(_GRP):
                f.write(f"    - {line_txt[len(_GRP):]}\n")
            elif line_txt.startswith(_DTA):
                lines = line_txt[len(_DTA):].split("\n")
                for j, sub in enumerate(lines):
                    if j == 0:
                        f.write(f"      {sub}\n")
                    else:
                        f.write(f"        {sub.lstrip()}\n")
            else:
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

    # 主进程预构建完整 GUID 映射，所有 worker/子进程共享（避免各自 os.walk）
    full_guid_map = {}
    if has_assets:
        _log("正在预构建 GUID 资源映射表（仅需一次遍历）...")
        full_guid_map = _build_full_guid_map(target_path)
        if full_guid_map:
            _log(f"  GUID 映射完成: {len(full_guid_map)} 项")

    output_dir = os.path.join(_script_dir, "语义分析")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"语义分析_{timestamp}.txt")

    _log(f"共 {len(sorted_revs)} 个版本待分析")

    if len(sorted_revs) > 1:
        _log(f"多版本模式（{len(sorted_revs)} 个版本），采用汇总分析（基准 r{max(1, min(sorted_revs)-1)} → 最新 r{max(sorted_revs)}）")
        all_results = [_analyze_squash_revisions(
            sorted_revs, source_url, full_guid_map, auth_args,
            rev_file_map=rev_file_map or {},
            target_path=target_path, _log=_log,
            svn_user=svn_user, svn_pass=svn_pass,
        )]
    else:
        max_workers = min(os.cpu_count() or 4, len(sorted_revs))
        chunks = _split_revisions(sorted_revs, max_workers)

        if len(chunks) <= 1:
            _log("单进程直接分析...")
            all_results = []
            for idx, rev in enumerate(sorted_revs):
                _log(f"正在分析 r{rev} ({idx+1}/{len(sorted_revs)})...")
                file_list = (rev_file_map or {}).get(str(rev))
                rd = _analyze_revision_data(rev, source_url, full_guid_map, auth_args, file_list=file_list, target_path=target_path, _log=_log)
                all_results.append(rd)
        else:
            _log(f"启动 {len(chunks)} 个子进程并行分析...")
            all_results = _run_parallel_analysis(
                chunks, source_url, full_guid_map, svn_user, svn_pass, sorted_revs, _log,
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
    running = {}
    stderr_threads = {}
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
        t = threading.Thread(target=_pipe_stderr_to_log, args=(proc, _log), daemon=True)
        t.start()
        stderr_threads[proc] = t

    done = 0
    total = len(sorted_revs)
    while running:
        finished = []
        for proc in list(running):
            rc = proc.poll()
            if rc is None:
                continue
            arg_path, res_path, chunk_revs = running[proc]
            finished.append(proc)

            stderr_threads[proc].join(timeout=2)

            if rc == 0 and os.path.getsize(res_path) > 0:
                try:
                    with open(res_path, "rb") as f:
                        chunk_data = pickle.load(f)
                    all_data.extend(chunk_data)
                except Exception as e:
                    _log(f"  子进程结果读取失败: {e}", "warn")
            else:
                _log(f"  子进程退出码 {rc}", "warn")

            # 立即删除临时文件
            for p in (arg_path, res_path):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                        _WORKER_TEMPFILES.remove(p)
                except (ValueError, OSError):
                    pass

            done += len(chunk_revs)
            if done % 5 == 0 or done == total:
                _log(f"  分析进度: {done}/{total}")

        for proc in finished:
            del running[proc]
            del stderr_threads[proc]

        if not finished:
            time.sleep(0.2)

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
