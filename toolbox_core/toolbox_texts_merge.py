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
    put(f"  版本对: {len(pairs)} 对\n")

    # ── Step 2: 下载并比较差异 ──
    put("  对比中...\n")
    try:
        # 传目录 URL（非文件 URL）使 svn_diff_filter 生效
        results, header_data, sheet_order = step3_download_and_compare(
            source_url, file_pairs=filtered_pairs,
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

    # ── Step 3: 子进程合并到目标（openpyxl 重活放子进程，避免占主进程 GIL）──
    # results 结构: {文件名: [行dict, ...]}，每个行dict含 ID、sheet、各列值
    # header_data 结构: {文件名: {sheet名: {行号: {列字母: 表头值}}}}
    put(f"  合并到目标: {local_file}\n")

    from toolbox_xlsx_merge import run_xlsx_apply_worker
    wr = run_xlsx_apply_worker({
        "mode": "merge_sheet_rows",
        "target_path": local_file,
        "title_rows": title_rows,
        "id_col": id_col,
        "diff_data": results,
        "header_data": header_data.get(next(iter(results)), {}) if header_data and results else {},
    }, put)

    if not wr or not wr.get("ok"):
        put("  合并到目标失败（子进程）\n")
        return 0, 1

    total_added = wr.get("added", 0)
    total_updated = wr.get("updated", 0)
    put(f"[Texts.xlsm] 合并完成: {total_updated} 行修改, {total_added} 行新增\n")
    return total_added + total_updated, 0
