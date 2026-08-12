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
        put(f"SVN 锁定: {local_file}\n")
        if not lock_fn(local_file):
            put("锁定失败，跳过 Texts.xlsm 合并\n")
            return 0, 1

    file_url = source_url.rstrip("/") + "/" + file_path
    put(f"[Texts.xlsm] 对比版本: {sorted(file_revs)}\n")

    # ── Step 1: 查版本对 ──
    from svn_oneclick_compare import step1_query_file_pairs, step3_download_and_compare, _log as _cmp_log
    import svn_oneclick_compare as _cmp_mod

    # 临时替换对比模块的日志输出，使日志进入执行面板
    _orig_log = _cmp_mod._log
    def _redirect_log(*a, **kw):
        try:
            msg = " ".join(str(x) for x in a)
            put(msg + "\n")
        except Exception:
            pass
    _cmp_mod._log = _redirect_log

    query_start = start_date or "2000-01-01"
    query_end = end_date or "2099-12-31"

    try:
        file_pairs, is_direct = step1_query_file_pairs(
            file_url, query_start, query_end,
            svn_user=svn_user or "", svn_pass=svn_pass or "")
    except Exception as e:
        _cmp_mod._log = _orig_log
        put(f"  版本查询失败: {e}\n")
        return 0, 0

    if not file_pairs:
        put("  未找到版本对，跳过\n")
        return 0, 0

    # 只保留选中版本
    selected_set = set(file_revs)
    filtered_pairs = {}
    for fname, pairs in file_pairs.items():
        kept = [(c, p) for c, p in pairs if c in selected_set]
        if kept:
            filtered_pairs[fname] = kept
    if not filtered_pairs:
        put("  选中版本无匹配的对比对，跳过\n")
        return 0, 0

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
                r = title_rows + 1 + i
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
