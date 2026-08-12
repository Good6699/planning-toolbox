"""Texts.xlsm 单元格级逐版本合并模块"""
import io
import os
import re
import subprocess

import openpyxl


def svn_cat_rev(svn_exe, url, rev, auth_args):
    """用 svn cat 下载指定版本的文件内容，返回 bytes 或 None"""
    cmd = [svn_exe, "cat", "-r", str(rev), "--non-interactive",
           "--trust-server-cert"] + auth_args + [url]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = proc.communicate(timeout=180)
        if proc.returncode == 0 and stdout:
            return stdout
    except Exception:
        pass
    return None


def svn_get_prev_rev(svn_exe, url, rev, auth_args):
    """获取指定文件在 rev 之前的最近一个修改版本号"""
    cmd = [svn_exe, "log", "-l", "1", "-r", f"1:{rev - 1}",
           "--non-interactive", "--trust-server-cert",
           "--quiet"] + auth_args + [url]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = proc.communicate(timeout=30)
        if proc.returncode == 0:
            m = re.search(rb"^r(\d+)", stdout)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return rev - 1


def _cell_equal(a, b):
    """比较两个单元格值是否相等"""
    return str(a or "") == str(b or "")


def extract_text_diffs(src_bytes, prev_bytes, title_rows, id_col):
    """比较两个版本的 Excel bytes，返回变更行。
    返回: list of (sheet_name, row_number)，1-based row indices in src_bytes"""
    try:
        wb_src = openpyxl.load_workbook(io.BytesIO(src_bytes), read_only=True, data_only=True)
        wb_prev = openpyxl.load_workbook(io.BytesIO(prev_bytes), read_only=True, data_only=True)
    except Exception:
        return []
    changed_rows = []
    for ws_name in wb_src.sheetnames:
        ws_src = wb_src[ws_name]
        ws_prev = wb_prev.get(ws_name)
        if ws_prev is None:
            for r in range(title_rows + 1, ws_src.max_row + 1):
                val = ws_src.cell(row=r, column=id_col).value
                if val is not None and str(val).strip():
                    changed_rows.append((ws_name, r))
            continue
        # 构建 prev 版本的 ID → 行数据映射
        prev_map = {}
        for r in range(title_rows + 1, ws_prev.max_row + 1):
            pid = ws_prev.cell(row=r, column=id_col).value
            if pid is None:
                continue
            pid_str = str(pid).strip()
            if not pid_str or pid_str in ("::ID::", "ID"):
                continue
            row_vals = {}
            for c in range(1, (ws_prev.max_column or 1) + 1):
                row_vals[c] = ws_prev.cell(row=r, column=c).value
            prev_map[pid_str] = row_vals
        # 比较 src 版本的每行
        for r in range(title_rows + 1, ws_src.max_row + 1):
            sid = ws_src.cell(row=r, column=id_col).value
            if sid is None:
                continue
            sid_str = str(sid).strip()
            if not sid_str or sid_str in ("::ID::", "ID"):
                continue
            if sid_str not in prev_map:
                changed_rows.append((ws_name, r))
                continue
            prev_row = prev_map[sid_str]
            for c in range(1, (ws_src.max_column or 1) + 1):
                sv = ws_src.cell(row=r, column=c).value
                pv = prev_row.get(c)
                if not _cell_equal(sv, pv):
                    changed_rows.append((ws_name, r))
                    break
    try:
        wb_src.close()
        wb_prev.close()
    except Exception:
        pass
    return changed_rows


def merge_texts_xlsm(source_url, target_path, file_path, file_revs,
                     svn_user, svn_pass, title_rows, id_col,
                     merge_sheet_rows_fn, put, lock_fn=None):
    """对 Texts.xlsm 做单元格级逐版本合并。
    merge_sheet_rows_fn: 外部传入的 _merge_sheet_rows 函数引用"""
    auth_args = []
    if svn_user:
        auth_args += ["--username", svn_user]
    if svn_pass:
        auth_args += ["--password", svn_pass]

    from toolbox_platform import _get_svn_path
    svn = _get_svn_path()

    file_url = source_url.rstrip("/") + "/" + file_path
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

    sorted_revs = sorted(file_revs)
    total_added = 0
    total_updated = 0

    for rev in sorted_revs:
        prev_rev = svn_get_prev_rev(svn, file_url, rev, auth_args)
        put(f"版本 {rev} (基准: {prev_rev}): 下载中...\n")

        cur_bytes = svn_cat_rev(svn, file_url, rev, auth_args)
        prev_bytes = svn_cat_rev(svn, file_url, prev_rev, auth_args)
        if not cur_bytes:
            put(f"  无法下载版本 {rev}，跳过\n")
            continue
        if not prev_bytes:
            put(f"  无法下载基准版本 {prev_rev}，跳过\n")
            continue

        diffs = extract_text_diffs(cur_bytes, prev_bytes, title_rows, id_col)
        if not diffs:
            put(f"  版本 {rev}: 无差异\n")
            continue

        by_sheet = {}
        for sheet_name, row_num in diffs:
            by_sheet.setdefault(sheet_name, []).append(row_num)

        try:
            wb_tgt = openpyxl.load_workbook(local_file)
        except Exception as e:
            put(f"  无法打开目标文件: {e}\n")
            continue

        wb_src = openpyxl.load_workbook(io.BytesIO(cur_bytes), read_only=True, data_only=True)
        added = 0
        updated = 0
        for sheet_name, rows in by_sheet.items():
            ws_src = wb_src.get(sheet_name)
            ws_tgt = wb_tgt.get(sheet_name)
            if not ws_src or not ws_tgt:
                continue
            a, u, _ = merge_sheet_rows_fn(ws_src, ws_tgt, rows, title_rows, id_col, set(), put)
            added += a
            updated += u

        try:
            wb_src.close()
        except Exception:
            pass

        try:
            wb_tgt.save(local_file)
            wb_tgt.close()
        except Exception as e:
            put(f"  保存失败: {e}\n")
            continue

        total_added += added
        total_updated += updated
        put(f"  版本 {rev}: {updated} 行修改, {added} 行新增\n")

    put(f"[Texts.xlsm] 合并完成: {total_updated} 行修改, {total_added} 行新增\n")
    return total_added + total_updated, 0
