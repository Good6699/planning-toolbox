"""Texts.xlsm 单元格级逐版本合并模块
完全复用 SVN对比Excel + 合并文字表 两个现有流程"""
import os
import tempfile


def merge_texts_xlsm(source_url, target_path, file_path, file_revs,
                     svn_user, svn_pass, title_rows, id_col,
                     exec_merge_table_fn, put, lock_fn=None,
                     start_date=None, end_date=None):
    """对 Texts.xlsm 做单元格级逐版本合并。
    完全复用 svn_oneclick_compare 对比流程 + _exec_merge_table 合并流程。
    exec_merge_table_fn: 外部传入的 _exec_merge_table 函数引用
    start_date/end_date: 筛选日期范围（从合并查询传入）"""
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

    # 构建 file_url（Texts.xlsm 的完整 SVN URL）
    file_url = source_url.rstrip("/") + "/" + file_path

    put(f"[Texts.xlsm] 对比版本: {sorted(file_revs)}\n")

    # ── Step 1: 用对比 Excel 流程获取差异 ──
    from svn_oneclick_compare import step1_query_file_pairs, step3_download_and_compare, write_excel

    # 用日期范围查询文件版本对；如果没传日期，用宽范围
    query_start = start_date or "2000-01-01"
    query_end = end_date or "2099-12-31"

    try:
        file_pairs, is_direct = step1_query_file_pairs(
            file_url, query_start, query_end,
            svn_user=svn_user or "", svn_pass=svn_pass or "")
    except Exception as e:
        put(f"  版本查询失败: {e}\n")
        return 0, 0

    if not file_pairs:
        put("  未找到版本对，跳过\n")
        return 0, 0

    # 只保留选中版本的对比对
    selected_set = set(file_revs)
    filtered_pairs = {}
    for fname, pairs in file_pairs.items():
        kept = [(c, p) for c, p in pairs if c in selected_set]
        if kept:
            filtered_pairs[fname] = kept
    if not filtered_pairs:
        put("  选中版本无匹配的对比对，跳过\n")
        return 0, 0

    put(f"  对比中...\n")
    try:
        results, header_data, sheet_order = step3_download_and_compare(
            file_url, file_pairs=filtered_pairs,
            svn_user=svn_user or "", svn_pass=svn_pass or "")
    except Exception as e:
        put(f"  对比失败: {e}\n")
        return 0, 0

    if not results:
        put("  无差异\n")
        return 0, 0

    # ── Step 2: 把差异写入临时 Excel 文件 ──
    tmp_dir = tempfile.mkdtemp(prefix="texts_merge_")
    diff_files = []
    for fname, rows in results.items():
        if not rows:
            continue
        out_path = os.path.join(tmp_dir, fname)
        try:
            write_excel(rows, out_path, title_rows=title_rows,
                        header_data=header_data, sheet_order=sheet_order)
            diff_files.append(out_path)
            put(f"  差异文件: {fname} ({len(rows)} 行)\n")
        except Exception as e:
            put(f"  写入差异文件失败: {fname} → {e}\n")

    if not diff_files:
        put("  无有效差异文件\n")
        return 0, 0

    # ── Step 3: 用合并文字表流程把差异合并到目标 ──
    target_dir = os.path.dirname(local_file)
    step = {
        "input_dir": tmp_dir,
        "target_dir": target_dir,
        "title_rows": title_rows,
        "id_col": id_col,
    }
    put(f"  合并到目标: {local_file}\n")
    try:
        ok = exec_merge_table_fn(step, put)
        if ok:
            put("[Texts.xlsm] 合并完成\n")
            return 1, 0
        else:
            put("[Texts.xlsm] 合并失败\n")
            return 0, 0
    except Exception as e:
        put(f"[Texts.xlsm] 合并异常: {e}\n")
        return 0, 0
