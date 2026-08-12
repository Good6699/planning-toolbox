"""Texts.xlsm 单元格级逐版本合并模块
复用 SVN对比Excel 的下载/比较流程，复用合并文字表的 _merge_sheet_rows 逻辑"""
import io
import os

import openpyxl


def merge_texts_xlsm(source_url, target_path, file_path, file_revs,
                     svn_user, svn_pass, title_rows, id_col,
                     merge_sheet_rows_fn, put, lock_fn=None,
                     start_date=None, end_date=None):
    """对 Texts.xlsm 做单元格级逐版本合并。
    1. 用 step1_query_file_pairs 查版本对
    2. 用 step3_download_and_compare 下载并比较差异
    3. 直接用 _merge_sheet_rows 把差异行合并到目标（跳过 write_excel）"""
    local_file = os.path.join(target_path, file_path.replace("/", os.sep))
    if not os.path.isfile(local_file):
        put(f"目标文件不存在，跳过: {local_file}\n")
        return 0, 0

    # SVN 锁定
    if lock_fn:
        if not lock_fn(local_file):
            put("锁定失败，跳过 Texts.xlsm 合并\n")
            return 0, 1

    file_url = source_url.rstrip("/") + "/" + file_path
    put(f"[Texts.xlsm] 对比版本: {sorted(file_revs)}\n")

    # ── Step 1: 自己构建版本对（跳过 step1_query_file_pairs 避免扫描全目录）──
    from svn_oneclick_compare import step3_download_and_compare
    import svn_oneclick_compare as _cmp_mod
    from toolbox_merge import svn_log

    # 临时替换对比模块的日志输出，使日志进入执行面板
    _orig_log = _cmp_mod._log
    def _redirect_log(*a, **kw):
        try:
            msg = " ".join(str(x) for x in a)
            put(msg + "\n")
        except Exception:
            pass
    _cmp_mod._log = _redirect_log

    # 用 svn_log 查文件在选中版本范围内的历史，构建版本对
    min_rev = min(file_revs)
    max_rev = max(file_revs)
    query_start = start_date or "2000-01-01"
    query_end = end_date or "2099-12-31"
    try:
        versions = svn_log(file_url, query_start, query_end,
                           svn_user=svn_user or "", svn_pass=svn_pass or "")
    except Exception as e:
        _cmp_mod._log = _orig_log
        put(f"  版本查询失败: {e}\n")
        return 0, 0

    # 文件在日期范围内的所有版本号（降序）
    file_all_revs = sorted([v["rev"] for v in versions if isinstance(v.get("rev"), int)], reverse=True)
    if not file_all_revs:
        _cmp_mod._log = _orig_log
        put("  文件无版本历史，跳过\n")
        return 0, 0

    rev_to_idx = {r: i for i, r in enumerate(file_all_revs)}
    selected_set = set(file_revs)

    # 为每个选中版本找到实际前一版本
    pairs = []
    for cur_rev in sorted(file_revs, reverse=True):
        if cur_rev not in rev_to_idx:
            continue
        idx = rev_to_idx[cur_rev]
        if idx + 1 < len(file_all_revs):
            prev_rev = file_all_revs[idx + 1]
            pairs.append((cur_rev, prev_rev))
        # 如果是最早版本，没有前一版本，跳过

    if not pairs:
        _cmp_mod._log = _orig_log
        put("  无有效版本对，跳过\n")
        return 0, 0

    fname = os.path.basename(file_path)
    filtered_pairs = {fname: pairs}
    put(f"  版本对: {[(c, p) for c, p in pairs]}\n")

    # ── Step 2: 下载并比较差异 ──
    put("  对比中...\n")
    try:
        results, header_data, sheet_order = step3_download_and_compare(
            file_url, file_pairs=filtered_pairs,
            svn_user=svn_user or "", svn_pass=svn_pass or "")
    except Exception as e:
        _cmp_mod._log = _orig_log
        put(f"  对比失败: {e}\n")
        return 0, 0

    # 恢复原始日志
    _cmp_mod._log = _orig_log

    if not results:
        put("  无差异\n")
        return 0, 0

    # ── Step 3: 直接用差异数据合并到目标 ──
    # results 结构: {文件名: [行dict, ...]}，每个行dict含 ID、sheet、各列值
    # 按 sheet 分组，提取行号列表，调用 _merge_sheet_rows
    put(f"  合并到目标: {local_file}\n")

    try:
        wb_tgt = openpyxl.load_workbook(local_file)
    except Exception as e:
        put(f"  无法打开目标文件: {e}\n")
        return 0, 0

    total_added = 0
    total_updated = 0

    for fname, rows in results.items():
        if not rows:
            continue

        # 调试：打印差异行详情
        for r in rows:
            put(f"  diff: 操作={r.get('操作')}, sheet={r.get('sheet')}, ID={r.get('ID')}\n")

        # 按 sheet 分组
        by_sheet = {}
        for row_data in rows:
            sheet_name = row_data.get("sheet", "")
            if not sheet_name:
                continue
            by_sheet.setdefault(sheet_name, []).append(row_data)

        # header_data 结构: {文件名: {sheet名: {行号: {列字母: 表头值}}}}
        file_hd = header_data.get(fname, {}) if header_data else {}

        for sheet_name, sheet_rows in by_sheet.items():
            ws_tgt = wb_tgt[sheet_name] if sheet_name in wb_tgt.sheetnames else None
            if not ws_tgt:
                put(f"  目标 sheet '{sheet_name}' 不存在，跳过\n")
                continue

            # 构建临时 worksheet
            wb_tmp = openpyxl.Workbook()
            ws_tmp = wb_tmp.active
            ws_tmp.title = sheet_name

            # 写入表头
            sheet_hd = file_hd.get(sheet_name, {})
            for row_num, cols in sheet_hd.items():
                for letter, val in cols.items():
                    col_num = openpyxl.utils.column_index_from_string(letter)
                    ws_tmp.cell(row=row_num, column=col_num, value=val)

            # 构建列名 → 列号映射
            col_name_map = {}
            if title_rows in sheet_hd:
                for letter, hdr_val in sheet_hd[title_rows].items():
                    col_num = openpyxl.utils.column_index_from_string(letter)
                    col_name_map[hdr_val] = col_num

            put(f"  {sheet_name}: 表头映射 {col_name_map}, 差异 {len(sheet_rows)} 行\n")

            # 写入差异行数据
            skip_keys = {"操作", "当前版本", "上一版本", "前一版本", "sheet",
                         "_id_changed", "前一版本_ID", "前一版本_SC", "前一版本_sub"}
            inp_rows = []
            for i, row_data in enumerate(sheet_rows):
                # 跳过删除行——源版本中被删除的行不应写入目标
                if row_data.get("操作") == "删除":
                    continue
                r = title_rows + 1 + len(inp_rows)
                inp_rows.append(r)
                for col_name, val in row_data.items():
                    if col_name in skip_keys:
                        continue
                    col_num = col_name_map.get(col_name)
                    if col_num:
                        ws_tmp.cell(row=r, column=col_num, value=val)

            if inp_rows:
                a, u, _ = merge_sheet_rows_fn(ws_tmp, ws_tgt, inp_rows, title_rows, id_col, set(), put)
                total_added += a
                total_updated += u
                put(f"  {sheet_name}: {u} 修改, {a} 新增\n")

            wb_tmp.close()

    try:
        wb_tgt.save(local_file)
        wb_tgt.close()
    except Exception as e:
        put(f"  保存失败: {e}\n")
        return 0, 0

    put(f"[Texts.xlsm] 合并完成: {total_updated} 行修改, {total_added} 行新增\n")
    return total_added + total_updated, 0
