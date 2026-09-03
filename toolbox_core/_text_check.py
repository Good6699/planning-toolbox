#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文字表检测引擎 — 检测 Texts.xlsm 的翻译质量问题"""

import os
import re
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from copy import copy
import sys

# 语言列（排除了 Time/Type/SubstituteId 等非语言列）
LANG_COLS = ["::EN::", "::IN::", "::TH::", "::RU::", "::FR::", "::GE::",
             "::TR::", "::SP::", "::PT::", "::KR::", "::TW::", "::JP::"]

# 占位符正则（提取具体占位符值用于精确匹配）
PLACEHOLDER_RE = re.compile(r'\{(\d+)\}|%[.\d]*[sdfgeE%]')

# 游戏格式串（如 [!0] [!1] [!2!] 等）
GAME_FMT_RE = re.compile(r'\[!\w+\]|\[!\d+!\]')

# 标签正则：<tag>、</tag>、<tag=value>、[tag]、[/tag]、[tag=value]
# 注意：不匹配 [中文内容]（避免噪声）
TAG_RE = re.compile(r'</?\w+(?:=\s*"[^"]*"|[^>]*)?>|\[/?\w+(?:=[^\[\]]+)?\]', re.ASCII)

# 需成对闭合的标签（游戏中真实成对出现）；其余（<Item>/<Image>/<timetag>/<br> 等）
# 为自闭合标签或普通文字内容，不参与配对检查
PAIR_TAGS = {"color", "gradient", "size", "careerid", "link", "i"}

# 标签配对规则：size/color/link 为行内样式标签，允许交叉/重叠嵌套；
# gradient/i/careerid 必须严格 LIFO 嵌套；所有标签都必须「先开再关」。
FLEX_TAGS = {"size", "color", "link"}
STRICT_TAGS = {"careerid", "i", "gradient"}

# 颜色代码验证
COLOR_HEX_RE = re.compile(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?|#[0-9a-fA-F]{3}')

# 命名色（游戏文本引擎支持的常见颜色名，如 <color=yellow>）
NAMED_COLORS = {"red", "green", "blue", "white", "black", "yellow", "cyan", "magenta",
                "gray", "grey", "orange", "pink", "purple", "brown", "gold", "silver"}

# 样式
FILL_RED = PatternFill(start_color="FFD7D7", end_color="FFD7D7", fill_type="solid")      # 漏翻/错误
FILL_YELLOW = PatternFill(start_color="FFFFD7", end_color="FFFFD7", fill_type="solid")    # 占位符不一致
FILL_ORANGE = PatternFill(start_color="FFE8CC", end_color="FFE8CC", fill_type="solid")    # 标签丢失/格式串不一致
FILL_PINK = PatternFill(start_color="FFD0E0", end_color="FFD0E0", fill_type="solid")      # 颜色码格式错误
FILL_GRAY = PatternFill(start_color="E8E8E8", end_color="E8E8E8", fill_type="solid")      # SC为空
FONT_RED = Font(color="CC0000")  # 重复ID


def _get_sc_idx(headers):
    for i, h in enumerate(headers):
        if h.strip().upper() == "::SC::":
            return i
    return -1


def _get_lang_idx_map(headers, target_langs=None, lang_id_map=None):
    """返回 {col_name: index}，只包括识别到的语言列
    target_langs: 列头或语言名称列表，如 ["::EN::", "韩文"]
    lang_id_map: 语言名称→ID列表映射，用于将名称解析为列头"""
    m = {}
    # 构建所有可能的匹配值
    check_vals = set()
    if target_langs:
        for tl in target_langs:
            tl_up = tl.upper()
            check_vals.add(tl_up)
            # 如果 lang_id_map 有该语言名，加入它的所有 ID
            if lang_id_map and tl in lang_id_map:
                for id_str in lang_id_map[tl]:
                    check_vals.add(id_str.strip().upper())
    else:
        check_vals = set(l.upper() for l in LANG_COLS)

    for i, h in enumerate(headers):
        key = h.strip().upper()
        if key in check_vals:
            m[h.strip()] = i
    return m


def _extract_placeholders(text):
    """提取占位符的具体值，如 {0} %s %d 等"""
    if not text:
        return set()
    return set(re.findall(r'\{(\d+)\}|%[.\d]*[sdfgeE%]', str(text)))


def _extract_tags(text):
    """提取标签完整内容，用于精确对比"""
    if not text:
        return set()
    return set(TAG_RE.findall(str(text)))


def _check_tag_pairing(text):
    """检查文本内标签是否配对（开标签有对应闭标签）。
    只检查配对正确性，不检查标签的值/颜色/位置——翻译时标签位置和颜色变化不算错误。

    方括号 [xxx] 只有成对出现（[tag]...[/tag]）才视为标签参与检查；
    单独出现的 [xxx] 是普通括号标注（如任务名 [Power Up]），不算标签。
    HTML 标签只对 PAIR_TAGS 中真实成对的标签做配对检查（大小写不敏感），
    其余（<Item ...>、<Image ...>、<timetag:...>、<br>、普通文字等）视为自闭合，不参与配对。

    标签配对规则：
    - size/color/link（行内样式）：允许交叉/重叠嵌套，只校验「先开再关 + 数量平衡」；
    - gradient/i/careerid（结构标签）：必须严格 LIFO 嵌套；
    - 所有标签都必须先开再关（只关不开/孤立闭标签、只开不关，均报错）。

    返回问题列表，如 ['缺少闭标签: <color=#ff6400ff>', '多余闭标签: </color>']"""
    issues = []
    if not text:
        return issues
    t = str(text)
    # 收集方括号标签名：只把「既有开也有闭」的方括号标签视为真标签
    bracket_open = set()
    bracket_close = set()
    for raw in TAG_RE.findall(t):
        if raw.startswith("["):
            if raw.startswith("[/"):
                bracket_close.add(raw[2:].split("]", 1)[0].strip().lower())
            else:
                inner = raw[1:].rstrip("]")
                bracket_open.add(re.split(r"[=\s]", inner, 1)[0].strip().lower())
    paired_bracket = bracket_open & bracket_close

    flex_stack: dict = {}  # name -> [未闭合开标签raw]（FLEX：仅平衡+先开再关）
    strict_stack = []      # [(name, raw)]（STRICT：严格 LIFO 嵌套）

    for m in TAG_RE.finditer(t):
        raw = m.group(0)
        is_bracket = raw.startswith("[")
        is_close = raw.startswith("</") or raw.startswith("[/")
        # 提取标签名（统一小写，大小写不敏感配对，如 <Size=23> 与 </size>）
        if is_close:
            if raw.startswith("</"):
                name = raw[2:].split(">", 1)[0].strip()
            else:
                name = raw[2:].split("]", 1)[0].strip()
        else:
            if raw.startswith("<"):
                inner = raw[1:].rstrip(">")
            else:
                inner = raw[1:].rstrip("]")
            name = re.split(r"[=\s]", inner, 1)[0].strip()
        name = name.lower()
        # 方括号标签不成对出现 → 普通括号内容，跳过
        if is_bracket and name not in paired_bracket:
            continue
        # 非配对 HTML 标签（自闭合 <Item>/<Image>/<timetag>/<br> 或普通文字）→ 跳过
        if not is_bracket and name not in PAIR_TAGS:
            continue
        if is_close:
            if name in FLEX_TAGS:
                # FLEX：只关掉最近一个未闭合的同名开标签；没有则先关后开→报错
                s = flex_stack.get(name)
                if s:
                    s.pop()
                else:
                    issues.append(f"多余闭标签: {raw}")
            else:
                # STRICT：严格 LIFO，中间未闭合的严格标签报缺少闭标签
                found = -1
                for i in range(len(strict_stack) - 1, -1, -1):
                    if strict_stack[i][0] == name:
                        found = i
                        break
                if found >= 0:
                    for i in range(len(strict_stack) - 1, found, -1):
                        issues.append(f"缺少闭标签: {strict_stack[i][1]}")
                    strict_stack = strict_stack[:found]
                else:
                    issues.append(f"多余闭标签: {raw}")
        else:
            # 裸标签（仅 <name>，无 =/属性）且同类型已有未闭合开标签 → 疑似闭标签漏写斜杠
            is_bare = (not is_bracket) and re.fullmatch(r"<[A-Za-z][A-Za-z0-9]*>", raw) is not None
            if is_bare and name in FLEX_TAGS:
                s = flex_stack.get(name)
                if s:
                    issues.append(f"标签闭合错误: {raw} 疑似应为 </{name}>")
                    s.pop()
                    continue
            if name in FLEX_TAGS:
                flex_stack.setdefault(name, []).append(raw)
            else:
                strict_stack.append((name, raw))
    # 剩余未闭合的开标签
    for name, raws in flex_stack.items():
        for raw in raws:
            issues.append(f"缺少闭标签: {raw}")
    for _, raw in strict_stack:
        issues.append(f"缺少闭标签: {raw}")
    return issues


def _extract_game_fmt(text):
    """提取游戏格式串如 [!0] [!1] [!2!]"""
    if not text:
        return set()
    return set(GAME_FMT_RE.findall(str(text)))


def _detect_mojibake(text):
    """检测乱码（UTF-8 解码错误导致的不可读字符）。

    注意：' ’ – — 是合法 Unicode 标点，â 是葡萄牙语合法字符（lâmpada、mágica），
    都不应判为乱码。只匹配真正的双重编码组合（UTF-8 被 Latin-1 误解码产生）。
    """
    if not text:
        return False
    t = str(text)
    # 真正的乱码组合（Latin-1 误解码 UTF-8）：' → â€™, – → â€", — → â€”, " → â€œ,
    # é → Ã©, ä → Ã¤, ü → Ã¼, ñ → Ã±, è → Ã¨, ö → Ã¶, ë → Ã«, î → Ã®, ô → Ã´, û → Ã»
    mojibake_patterns = [
        "â€™", "â€\u201d", "â€\u201c", "â€˜", "â€š", "â€\u2013", "â€\u2014",
        "Ã©", "Ã¤", "Ã¼", "Ã±", "Ã¨", "Ã¶", "Ã«", "Ã®", "Ã´", "Ã¹", "Ã¢", "Ã£", "Ã§",
        "\ufffd",  # Replacement character
    ]
    for pat in mojibake_patterns:
        if pat in t:
            return True
    # 检查是否包含连续的 Latin-1 控制字符（常见于 GBK 误解码）
    latin1_count = sum(1 for c in t if "\x80" <= c <= "\x9f")
    if latin1_count > len(t) * 0.2:  # 超过 20% 的字符是 Latin-1 控制字符
        return True
    return False


def _check_whitespace(sc_text, lang_text):
    """检查首尾空白是否一致"""
    issues = []
    sc_strip = sc_text.strip()
    lang_strip = lang_text.strip()
    # 前导空白
    sc_lead = sc_text[:len(sc_text) - len(sc_strip)]
    lang_lead = lang_text[:len(lang_text) - len(lang_strip)]
    if sc_lead != lang_lead:
        issues.append("前导空格不一致")
    # 尾部空白
    sc_trail = sc_text[len(sc_strip):]
    lang_trail = lang_text[len(lang_strip):]
    if sc_trail != lang_trail:
        issues.append("尾部空格不一致")
    return issues


def _validate_color_codes(text):
    """检查文本中的颜色代码格式是否正确"""
    if not text:
        return []
    issues = []
    # 匹配 <color=#...> 中的颜色值
    for m in re.finditer(r'<color=([^>]+)>', str(text)):
        val = m.group(1).strip()
        if "{" in val or "}" in val:
            continue  # 占位符颜色（如 <color=#{{{2}}}>）→ 动态值，跳过
        if val.lower() in NAMED_COLORS:
            continue  # 命名色（如 <color=yellow>）→ 引擎支持，跳过
        if not COLOR_HEX_RE.fullmatch(val):
            issues.append(val)
    return issues


def _issue_cat_rank(issue: str) -> int:
    """根据第一条检测结果判定分类排序优先级（数字越小越靠前，按用户确认的顺序）。"""
    if not issue:
        return 99
    s = str(issue)
    if "ID重复" in s:
        return 1
    if "SC颜色码格式错误" in s:
        return 2
    if "标签闭合错误" in s:
        return 3
    if "缺少闭标签" in s:
        return 4
    if "多余闭标签" in s:
        return 5
    if "占位符不一致" in s:
        return 6
    if "缺少格式串" in s:
        return 7
    if "多余格式串" in s:
        return 8
    if "颜色码格式错误" in s:
        return 9
    if "空格不一致" in s:
        return 10
    if "疑似乱码" in s:
        return 11
    if "漏翻" in s:
        return 12
    if "SC列为空" in s:
        return 13
    return 99


def detect(input_path, progress_callback=None, target_langs=None, lang_id_map=None,
           exclude_ids_path=None):
    """
    主检测函数
    progress_callback(msg): 接收进度消息字符串
    target_langs: 要检测的语言列头列表，如 ["::EN::", "::KR::"]，None=检测全部
    lang_id_map: tr_lang_id_map 配置，用于将语言名称（"韩文"）解析为列头（"::KR::"）
    exclude_ids_path: 排除 ID 配置文件路径，一行一个 ID
    返回: (output_path, issues_count)
    """
    if not os.path.isfile(input_path):
        return None, f"文件不存在: {input_path}"

    # 加载排除 ID 列表和 SC 排除关键词
    exclude_ids = set()
    exclude_sc_keywords = []
    if exclude_ids_path and os.path.isfile(exclude_ids_path):
        with open(exclude_ids_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("KEYWORD:"):
                    kw = line[8:].strip()
                    if kw:
                        exclude_sc_keywords.append(kw)
                else:
                    exclude_ids.add(line.upper())
        if exclude_ids and progress_callback:
            progress_callback(f"  已加载 {len(exclude_ids)} 个排除 ID\n")
        if exclude_sc_keywords:
            progress_callback(f"  已加载 {len(exclude_sc_keywords)} 个排除关键词\n")

    # 统一排除关键词：内置规则 + 配置文件 KEYWORD: 条目，检查所有语言列（含SC）
    exclude_keywords = ["作废", "配了就是错"] + exclude_sc_keywords

    base_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(base_dir, f"{base_name}_检测结果.xlsx")

    wb = openpyxl.load_workbook(input_path, data_only=True)
    out_wb = openpyxl.Workbook()
    out_ws = out_wb.active
    out_ws.title = "检测结果"

    # 标题行
    out_ws.cell(row=1, column=1, value="检测结果")
    out_ws.cell(row=1, column=2, value="原Sheet表名")

    # ---- 第1遍：收集所有ID用于查重 ----
    all_id_map = {}  # id -> [(sheet_name, row_number)]
    if progress_callback:
        progress_callback(f"扫描 {len(wb.sheetnames)} 个 Sheet 收集 ID...\n")
    for sn in wb.sheetnames:
        ws = wb[sn]
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        id_idx = -1
        for i, h in enumerate(headers):
            if h.strip().upper() == "::ID::":
                id_idx = i
                break
        if id_idx < 0:
            continue
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[id_idx] is not None:
                sid = str(row[id_idx]).strip()
                if sid:
                    all_id_map.setdefault(sid, []).append((sn, row[id_idx]))

    duplicate_ids = {sid for sid, locs in all_id_map.items() if len(locs) > 1}

    # ---- 第2遍：逐行检测并写入 ----
    if progress_callback:
        progress_callback("逐行检测翻译质量...\n")
    out_row = 2
    rows_to_write = []  # (分类rank, sheet序号, 行号, result_text, sheet名, row, src_to_out, cell_colors, is_dup, id_idx)
    total_issues = 0
    processed_rows = 0
    master_headers_written = False
    master_headers = []
    src_to_out = {}
    sheet_count = len(wb.sheetnames)

    for si, sn in enumerate(wb.sheetnames):
        sheet_ord = si  # 保留 sheet 序号（内部 header 映射会用 si，会覆盖）
        if progress_callback:
            progress_callback(f"  正在检测 [{si+1}/{sheet_count}] {sn}\n")
        ws = wb[sn]
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]

        # 定位列
        id_idx = -1
        for i, h in enumerate(headers):
            if h.strip().upper() == "::ID::":
                id_idx = i
                break
        sc_idx = _get_sc_idx(headers)
        lang_map = _get_lang_idx_map(headers, target_langs, lang_id_map)

        if sc_idx < 0:
            continue  # 没有SC列，跳过

        # 关键词排除扫描的列：SC + 全部语言列（不受勾选语言限制）
        kw_lang_idx = [sc_idx] + list(_get_lang_idx_map(headers, None, lang_id_map).values())

        # 第一次运行时确定输出列顺序
        if not master_headers_written:
            # 将 target_langs 中的语言名称解析为列头
            resolved_langs = set()
            if target_langs:
                for tl in target_langs:
                    tl_up = tl.upper()
                    if tl_up.startswith("::") and tl_up.endswith("::"):
                        resolved_langs.add(tl_up)
                    elif lang_id_map and tl in lang_id_map:
                        for id_str in lang_id_map[tl]:
                            resolved_langs.add(id_str.strip().upper())
                    else:
                        resolved_langs.add(tl_up)
            else:
                resolved_langs = set(l.upper() for l in LANG_COLS)
            # 输出列：ID + SC + 勾选的语言
            out_col_names = ["::ID::", "::SC::"]
            # 按源表顺序添加勾选的语言列
            for h in headers:
                if h.strip().upper() in resolved_langs:
                    if h not in out_col_names:
                        out_col_names.append(h)
            # 构建源列索引 → 输出列索引映射
            src_to_out = {}
            for si, sh in enumerate(headers):
                if sh in out_col_names:
                    src_to_out[si] = out_col_names.index(sh) + 3  # +3=跳过检测结果+sheet名列
            # 写入输出表头
            for col_name, ci in [(n, out_col_names.index(n) + 3) for n in out_col_names]:
                out_ws.cell(row=1, column=ci, value=col_name)
            master_headers_written = True
            master_headers = out_col_names

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            processed_rows += 1
            if progress_callback and processed_rows % 5000 == 0:
                progress_callback(f"    已处理 {processed_rows} 行...\n")
            # 提取值
            id_val = str(row[id_idx]).strip() if row[id_idx] is not None else ""
            if not id_val:
                continue  # ID为空的行跳过
            if id_val.upper() in exclude_ids:
                continue  # 排除ID列表中的行跳过
            sc_val = str(row[sc_idx]).strip() if row[sc_idx] is not None else ""
            # 排除关键词（内置规则 + 配置 KEYWORD: 条目）统一检查所有列（含 ID 与语言列）
            lang_cells = [id_val, sc_val]
            for ci in kw_lang_idx:
                if row[ci] is not None:
                    lang_cells.append(str(row[ci]).strip())
            if any(kw in c for c in lang_cells for kw in exclude_keywords):
                continue  # 任一语言列含排除关键词则整行跳过
            if id_val.upper() == sc_val.upper() and len(id_val) > 3:
                continue  # ID和SC内容相同跳过（如 ID=XXX SC=XXX）
            issues = []
            cell_colors = {}  # col_index -> fill

            # --- 检测1: SC为空 ---
            if not sc_val:
                issues.append("SC列为空")
                cell_colors[sc_idx] = FILL_GRAY

            # --- 检测2: 漏翻 + 占位符 + 标签 + 格式串 + 颜色码 ---
            if sc_val:
                sc_placeholders = _extract_placeholders(sc_val)
                sc_game_fmt = _extract_game_fmt(sc_val)
                sc_color_issues = _validate_color_codes(sc_val)
                sc_len = len(sc_val)

                # SC 本身的颜色码格式检查
                for bad_color in sc_color_issues:
                    issues.append(f"SC颜色码格式错误: {bad_color}")

                for lang_name, col_idx in lang_map.items():
                    lang_val = str(row[col_idx]).strip() if row[col_idx] is not None else ""

                    # 漏翻
                    if not lang_val:
                        issues.append(f"{lang_name} 漏翻")
                        cell_colors[col_idx] = FILL_RED
                        continue

                    lang_placeholders = _extract_placeholders(lang_val)
                    lang_game_fmt = _extract_game_fmt(lang_val)

                    # 占位符具体值对比（不是只数数量）
                    if sc_placeholders != lang_placeholders:
                        issues.append(f"{lang_name} 占位符不一致")
                        cell_colors[col_idx] = FILL_YELLOW

                    # 标签配对检查：只检查目标语言内部标签是否成对闭合，
                    # 不对比源文本（翻译时标签位置/颜色变化不算错误）
                    for tag_issue in _check_tag_pairing(lang_val):
                        issues.append(f"{lang_name} {tag_issue}")
                        cell_colors[col_idx] = FILL_ORANGE

                    # 游戏格式串对比（[!0] 等）
                    if sc_game_fmt != lang_game_fmt:
                        missing = sc_game_fmt - lang_game_fmt
                        extra = lang_game_fmt - sc_game_fmt
                        if missing:
                            issues.append(f"{lang_name} 缺少格式串: {','.join(sorted(missing))}")
                        if extra:
                            issues.append(f"{lang_name} 多余格式串: {','.join(sorted(extra))}")
                        cell_colors[col_idx] = FILL_ORANGE

                    # 翻译语言的颜色码格式检查
                    lang_color_issues = _validate_color_codes(lang_val)
                    for bad_color in lang_color_issues:
                        issues.append(f"{lang_name}颜色码格式错误: {bad_color}")
                        cell_colors[col_idx] = FILL_PINK

                    # 空白字符一致性
                    ws_issues = _check_whitespace(sc_val, lang_val)
                    for wsi in ws_issues:
                        issues.append(f"{lang_name} {wsi}")
                        cell_colors[col_idx] = FILL_YELLOW

                    # 乱码检测
                    if _detect_mojibake(lang_val):
                        issues.append(f"{lang_name} 疑似乱码")
                        cell_colors[col_idx] = FILL_PINK


            # --- 检测3: 重复ID ---
            is_dup = id_val in duplicate_ids
            # 只在当前ID的第一次出现时标记重复，避免所有重复行都标记
            # 但用户要求检测出来，都标记更清晰

            # 组装结果说明
            result_text = "；".join(issues) if issues else ""
            # 重复ID单独处理
            dup_note = ""
            if is_dup:
                locs = all_id_map.get(id_val, [])
                other_sheets = [loc[0] for loc in locs if loc[0] != sn]
                if other_sheets:
                    dup_note = f"ID重复（{', '.join(other_sheets)}）"
                else:
                    dup_note = "ID重复（同Sheet内重复）"
                if result_text:
                    result_text = result_text + "；" + dup_note
                else:
                    result_text = dup_note

            if not result_text:
                continue  # 无问题行跳过

            # 收集待写行（用于分类排序）：先按第一条问题归类
            first_issue = issues[0] if issues else dup_note
            rows_to_write.append((_issue_cat_rank(first_issue), sheet_ord, row_idx,
                                  result_text, sn, list(row), src_to_out, dict(cell_colors), is_dup, id_idx))
            total_issues += 1

    # ---- 按（分类顺序, sheet顺序, 行顺序）排序后写入 ----
    rows_to_write.sort(key=lambda r: (r[0], r[1], r[2]))
    for (cat, sheet_ord, row_idx, result_text, sn, row, src_to_out, cell_colors, is_dup, id_idx) in rows_to_write:
        out_ws.cell(row=out_row, column=1, value=result_text)
        out_ws.cell(row=out_row, column=2, value=sn)
        for src_i, val in enumerate(row):
            if src_i not in src_to_out:
                continue
            c = out_ws.cell(row=out_row, column=src_to_out[src_i])
            if val is not None:
                c.value = val
            if src_i in cell_colors:
                c.fill = cell_colors[src_i]
            if is_dup and src_i == id_idx:
                c.font = FONT_RED
        out_row += 1

    # 样式（SVN 对比导出格式）
    header_fill = PatternFill("solid", fgColor="4472C4")
    header_font = Font(color="FFFFFF", bold=True)
    alt_fill = PatternFill("solid", fgColor="DCE6F1")
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # 表头锁（冻结首行）
    out_ws.freeze_panes = "A2"

    # 设置标题行样式
    max_widths = {i: len(str(c.value or "")) for i, c in enumerate(out_ws[1], 1)}
    for c in out_ws[1]:
        c.fill = header_fill
        c.font = header_font
        c.alignment = center
        c.border = border

    # 数据行样式（交替色 + 边框，跳过已有底色的问题单元格）
    for r in range(2, out_row):
        for i, c in enumerate(out_ws[r], 1):
            if c.fill == PatternFill(fill_type=None):
                c.fill = alt_fill if r % 2 == 0 else PatternFill()
            c.border = border
            # 自动列宽
            val_len = len(str(c.value or ""))
            max_widths[i] = max(max_widths.get(i, 10), val_len)

    # 设置列宽（自适应，最大 60）
    for col_idx, w in max_widths.items():
        out_ws.column_dimensions[get_column_letter(col_idx)].width = min(w + 2, 60)

    wb.close()
    if progress_callback:
        progress_callback(f"  正在写入结果文件（共 {total_issues} 行）...\n")
    try:
        out_wb.save(output_path)
        out_wb.close()
        if progress_callback:
            progress_callback(f"  结果文件已保存\n")
    except PermissionError:
        if progress_callback:
            progress_callback(f"[错误] 无法写入 {os.path.basename(output_path)}，文件正在被 Excel 打开，请关闭后重试\n")
        return output_path, total_issues
    except Exception as e:
        if progress_callback:
            progress_callback(f"[错误] 写入失败: {e}\n")
        return output_path, total_issues

    return output_path, total_issues


if __name__ == "__main__":
    path = r"F:\D3_KR2_DEV\gameData\Text\Texts.xlsm"
    out, count = detect(path)
    if out:
        print(f"检测完成! 输出: {out}")
        print(f"发现问题: {count} 行")
    else:
        print(f"错误: {count}")
