#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openpyxl 表合并核心函数（独立模块，供主进程与子进程 worker 共用）
包含：_merge_sheet_rows（单元格级按 ID 合并）、_copy_rows_by_id（整行按 ID 复制）、
_sync_index_table（文字索引表同步）、run_xlsx_apply_worker（子进程调度）"""

import os
import pickle
import subprocess
import sys
import tempfile


def run_xlsx_apply_worker(args, put, task_id=None, timeout=1200):
    """把 openpyxl 合并任务丢给 _xlsx_apply_worker 子进程执行（避免占主进程 GIL）。
    args: {"mode": "merge_sheet_rows"|"copy_rows_by_id"|"sync_index", ...}
    返回结果 dict {"ok","added","updated","logs"} 或 None（失败/超时）"""
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    worker_script = os.path.join(_script_dir, "_xlsx_apply_worker.py")
    fd1, arg_path = tempfile.mkstemp(suffix=".pkl", prefix="xlsx_arg_")
    os.close(fd1)
    fd2, res_path = tempfile.mkstemp(suffix=".pkl", prefix="xlsx_res_")
    os.close(fd2)
    proc = None
    try:
        with open(arg_path, "wb") as f:
            pickle.dump(args, f)
        _env = dict(os.environ)
        _env.setdefault("PYTHONIOENCODING", "utf-8")
        proc = subprocess.Popen(
            [sys.executable, worker_script, arg_path, res_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=_env)
        out_bytes, _ = proc.communicate(timeout=timeout)
        # 转发子进程日志
        try:
            out = out_bytes.decode("utf-8", errors="replace") if isinstance(out_bytes, bytes) else str(out_bytes)
            for line in out.splitlines():
                if line.strip():
                    put(line + "\n")
        except Exception:
            pass
        if proc.returncode != 0:
            put(f"  子进程退出码: {proc.returncode}\n")
        if os.path.isfile(res_path):
            with open(res_path, "rb") as f:
                return pickle.load(f)
    except subprocess.TimeoutExpired:
        put("  openpyxl 子进程超时\n")
        try:
            if proc:
                proc.kill()
                proc.communicate(timeout=5)
        except Exception:
            pass
        return None
    except Exception as e:
        put(f"  子进程异常: {e}\n")
        return None
    finally:
        for p in (arg_path, res_path):
            try:
                os.unlink(p)
            except Exception:
                pass
    return None


def _merge_sheet_rows(ws_in, ws_tgt, inp_rows, title_rows, id_col, dup_ids, put):
    """按 ID 合并 sheet：更新现有行、追加新增行。返回 (added, updated, source_ids)

    对齐 Tkinter 旧版逻辑：
    - ID 列按列头文字匹配
    - 数据列按 (列头, 出现次数) 元匹配（支持重复列头）
    - 连续数据区识别，END 标记处理：
      有 END 时旧 END 行变 "0"，新行插在 END 后，最后一行变 "END"
    - dup_ids: 跨 sheet 重复的 ID 集合，用于日志标注 """
    id_col_num = id_col
    if id_col_num > ws_tgt.max_column:
        return 0, 0, set()

    tgt_id_header = str(ws_tgt.cell(row=title_rows, column=id_col_num).value or "").strip()
    if not tgt_id_header:
        return 0, 0, set()

    inp_id_col = None
    for col in range(1, ws_in.max_column + 1):
        h = ws_in.cell(row=title_rows, column=col).value
        if h and str(h).strip() == tgt_id_header:
            inp_id_col = col
            break
    if inp_id_col is None:
        return 0, 0, set()

    # ── 查找连续数据区 ──
    last_continuous_id_row = title_rows
    for r in range(title_rows + 1, ws_tgt.max_row + 1):
        val = ws_tgt.cell(row=r, column=id_col_num).value
        if val is not None and str(val).strip():
            last_continuous_id_row = r
        else:
            break

    # ── 查找 END 标记 ──
    has_end = False
    end_row_at = None
    if last_continuous_id_row >= title_rows + 1:
        for r in range(last_continuous_id_row, ws_tgt.max_row + 1):
            val = ws_tgt.cell(row=r, column=1).value
            if val is not None and str(val).strip().lower() == "end":
                has_end = True
                end_row_at = r
                break

    # ── 构建目标 ID → 行号 映射（连续数据区内） ──
    tgt_id_map = {}
    for r in range(title_rows + 1, last_continuous_id_row + 1):
        val = ws_tgt.cell(row=r, column=id_col_num).value
        if val is not None:
            key = str(val).strip()
            if key:
                tgt_id_map[key] = r

    updated = 0
    source_ids = set()
    new_rows_data = []  # 待插入行的 (inp_id, col_data) 列表

    for inp_r in inp_rows:
        inp_id_val = ws_in.cell(row=inp_r, column=inp_id_col).value
        if inp_id_val is None:
            continue
        inp_id = str(inp_id_val).strip()
        if not inp_id or inp_id in ("::ID::", "ID"):
            continue
        source_ids.add(inp_id)

        # 读取输入行数据，按 (列头, 出现次数) 为 key（从列 2 开始，列 1 为 ID）
        inp_hdr_count = {}
        row_data = {}
        for col in range(2, ws_in.max_column + 1):
            h = ws_in.cell(row=title_rows, column=col).value
            if h is not None:
                h_str = str(h).strip()
                occ = inp_hdr_count.get(h_str, 0)
                inp_hdr_count[h_str] = occ + 1
                val = ws_in.cell(row=inp_r, column=col).value
                row_data[(h_str, occ)] = val

        if inp_id in tgt_id_map:
            # ── 更新：按目标列头匹配写入 ──
            tgt_r = tgt_id_map[inp_id]
            tgt_hdr_count = {}
            for col in range(1, ws_tgt.max_column + 1):
                h = ws_tgt.cell(row=title_rows, column=col).value
                if h is not None:
                    h_str = str(h).strip()
                    occ = tgt_hdr_count.get(h_str, 0)
                    tgt_hdr_count[h_str] = occ + 1
                    if h_str != tgt_id_header and col != 1:
                        key = (h_str, occ)
                        if key in row_data:
                            ws_tgt.cell(row=tgt_r, column=col).value = row_data[key]
            updated += 1
        else:
            # ── 插入：按目标列头匹配收集数据（跳过列 1） ──
            tgt_hdr_count = {}
            col_data = {}
            for col in range(1, ws_tgt.max_column + 1):
                h = ws_tgt.cell(row=title_rows, column=col).value
                if h is not None:
                    h_str = str(h).strip()
                    occ = tgt_hdr_count.get(h_str, 0)
                    tgt_hdr_count[h_str] = occ + 1
                    if col == 1:
                        continue
                    key = (h_str, occ)
                    if key in row_data:
                        col_data[col] = row_data[key]
            new_rows_data.append((inp_id, col_data))

    # ── 批量写入插入行 ──
    added = len(new_rows_data)
    if new_rows_data:
        if has_end:
            # END → "0"，新行插在 END 后，最后一行变 "END"
            ws_tgt.cell(row=end_row_at, column=1).value = "0"
            for col, val in new_rows_data[0][1].items():
                ws_tgt.cell(row=end_row_at, column=col).value = val
            for i in range(1, len(new_rows_data)):
                inp_id, col_data = new_rows_data[i]
                tgt_r = end_row_at + i
                col_data[1] = "0" if i < len(new_rows_data) - 1 else "END"
                for col, val in col_data.items():
                    ws_tgt.cell(row=tgt_r, column=col).value = val
        else:
            after_row = last_continuous_id_row
            for i, (inp_id, col_data) in enumerate(new_rows_data):
                col_data[1] = inp_id
                tgt_r = after_row + 1 + i
                for col, val in col_data.items():
                    ws_tgt.cell(row=tgt_r, column=col).value = val

    if added > 0 or updated > 0:
        put(f"    {ws_in.title}: 新增 {added} 行, 更新 {updated} 行\n")
    return added, updated, source_ids


def _copy_rows_by_id(wb_src, wb_tgt, id_by_sheet, title_rows, id_col, put):
    """按 ID 从来源表整行复制到目标表（列头名对应，值类型保持，目标缺失追加）。
    单遍 iter_rows 扫描，避免 read_only 工作表随机访问。返回 (added, updated)"""
    added = updated = 0
    for sheet_name, ids in id_by_sheet.items():
        if sheet_name not in wb_src.sheetnames or sheet_name not in wb_tgt.sheetnames:
            # 精确匹配失败：区分源/目标，列出目标表实际 sheet 名与相近候选，便于排查表结构差异
            if sheet_name not in wb_src.sheetnames:
                put(f"  sheet 缺失（源表无此 sheet）: {sheet_name}，跳过\n")
            else:
                put(f"  sheet 缺失（目标表无此 sheet）: {sheet_name}，跳过\n")
                cands = [sn for sn in wb_tgt.sheetnames
                         if sn.startswith(sheet_name) or sheet_name.startswith(sn)]
                if cands:
                    put(f"    相近候选（可能为分支改名的同一 sheet）: {', '.join(cands)}\n")
                else:
                    put(f"    目标表现有 sheet: {', '.join(wb_tgt.sheetnames)}\n")
            continue
        ws_src = wb_src[sheet_name]
        ws_tgt = wb_tgt[sheet_name]
        # 列头名 → 列号映射（源、目标各自，只读表头一行）
        src_col = {}
        tgt_col = {}
        for hdr_row in ws_src.iter_rows(min_row=title_rows, max_row=title_rows, values_only=True):
            for c, h in enumerate(hdr_row, start=1):
                if h is not None:
                    src_col[str(h).strip()] = c
        for hdr_row in ws_tgt.iter_rows(min_row=title_rows, max_row=title_rows, values_only=True):
            for c, h in enumerate(hdr_row, start=1):
                if h is not None:
                    tgt_col[str(h).strip()] = c
        # 源表 ID 列头名（源表按列号 id_col 定位）
        id_header = next((name for name, c in src_col.items() if c == id_col), None)
        if not id_header:
            put(f"  {sheet_name}: 未找到 ID 列，跳过\n")
            continue
        # 目标表 ID 列按列头名定位（列位置可能与源表不同）
        tgt_id_col = tgt_col.get(id_header)
        if not tgt_id_col:
            put(f"  {sheet_name}: 目标表无 ID 列，跳过\n")
            continue
        # 源表行索引：ID → (行号, 行值元组)，单遍迭代
        src_rows = {}
        for r, row in enumerate(ws_src.iter_rows(min_row=title_rows + 1, values_only=True),
                                start=title_rows + 1):
            v = row[id_col - 1] if len(row) >= id_col else None
            if v is None:
                continue
            sid = str(v).strip()
            if sid and sid in ids:
                src_rows.setdefault(sid, (r, row))
        if not src_rows:
            continue
        # 目标表行索引：ID → 行号，单遍迭代；同时定位 END 标记行
        # （第 1 列 = "end"，仅当 ID 列不在第 1 列时启用，避免把 ID 值当标记覆盖）
        tgt_rows = {}
        end_row_at = None
        for r, row in enumerate(ws_tgt.iter_rows(min_row=title_rows + 1, values_only=True),
                                start=title_rows + 1):
            if id_col != 1 and row and row[0] is not None and str(row[0]).strip().lower() == "end":
                end_row_at = r
            v = row[tgt_id_col - 1] if len(row) >= tgt_id_col else None
            if v is None:
                continue
            tgt_rows.setdefault(str(v).strip(), r)
        sh_added = sh_updated = 0
        new_rows = []  # 待新增的 (sid, srow)
        for sid in sorted(ids):
            if sid not in src_rows:
                continue
            _, srow = src_rows[sid]
            if sid in tgt_rows:
                tr = tgt_rows[sid]
                sh_updated += 1
                # 整行复制：按列头名对应，源有目标没有的列跳过；
                # 有 END 标记时第 1 列为标记列，不复制（保持目标原有标记）
                for name, sc in src_col.items():
                    if end_row_at is not None and sc == 1:
                        continue
                    tc = tgt_col.get(name)
                    if not tc:
                        continue
                    if sc - 1 < len(srow):
                        ws_tgt.cell(row=tr, column=tc).value = srow[sc - 1]
            else:
                new_rows.append((sid, srow))
        if new_rows:
            # 新增行：有 END 时追加到 END 行之后（原 END 行标记 → 0，数据不动），
            # 新行最后一行标记 → "END"，其余 → "0"；无 END 时直接追加表尾
            if end_row_at is not None:
                ws_tgt.cell(row=end_row_at, column=1).value = "0"
                start_r = end_row_at + 1
            else:
                start_r = ws_tgt.max_row + 1
            n = len(new_rows)
            for i, (sid, srow) in enumerate(new_rows):
                tr = start_r + i
                if end_row_at is not None:
                    ws_tgt.cell(row=tr, column=1).value = "END" if i == n - 1 else "0"
                for name, sc in src_col.items():
                    if end_row_at is not None and sc == 1:
                        continue
                    tc = tgt_col.get(name)
                    if not tc:
                        continue
                    if sc - 1 < len(srow):
                        ws_tgt.cell(row=tr, column=tc).value = srow[sc - 1]
            sh_added += n
        added += sh_added
        updated += sh_updated
        put(f"  {sheet_name}: {sh_updated} 替换, {sh_added} 新增\n")
    return added, updated


def _sync_index_table(src_path, tgt_path, changed_ids, put):
    """同步文字索引表（文字引用处理.xlsm）：只处理与变更文字ID相关的行，
    按列位置整行复制到目标（源/目标结构一致）。返回 (added, updated)"""
    import openpyxl
    if not os.path.isfile(src_path) or not os.path.isfile(tgt_path):
        put("  索引表缺失（源/目标），跳过\n")
        return 0, 0
    try:
        wb_src = openpyxl.load_workbook(src_path, read_only=True, data_only=True)
    except Exception as e:
        put(f"  读取源索引表失败: {e}\n")
        return 0, 0
    try:
        wb_tgt = openpyxl.load_workbook(tgt_path, keep_vba=True)
    except Exception as e:
        wb_src.close()
        put(f"  打开目标索引表失败: {e}\n")
        return 0, 0

    def _probe(ws):
        """探测：表头行（含 调用ID）、ID 列号、数据起始行（DataType 行之后）"""
        hdr_row = None
        id_col = None
        data_start = None
        for r in range(1, min(ws.max_row, 12) + 1):
            row_vals = next(ws.iter_rows(min_row=r, max_row=r, values_only=True), None)
            if row_vals is None:
                break
            if hdr_row is None:
                for c, v in enumerate(row_vals, start=1):
                    if v is not None and '调用ID' in str(v):
                        hdr_row = r
                        id_col = c
                        break
            if row_vals and row_vals[0] is not None and str(row_vals[0]).strip() == 'DataType':
                data_start = r + 1
                break
        return hdr_row, id_col, data_start

    added = updated = 0
    try:
        for sn in wb_src.sheetnames:
            if sn not in wb_tgt.sheetnames:
                put(f"  索引表 sheet 缺失（目标）: {sn}，跳过\n")
                continue
            ws_src = wb_src[sn]
            ws_tgt = wb_tgt[sn]
            hdr, idc, ds = _probe(ws_src)
            if not hdr or not idc or not ds:
                put(f"  索引表结构无法识别: {sn}，跳过\n")
                continue
            # 扫描源数据行：相关行 = 任一占位符列值命中变更文字ID
            related = {}  # 调用ID → (行号, 行值)
            for r, row in enumerate(ws_src.iter_rows(min_row=ds, values_only=True), start=ds):
                if not row or len(row) < idc:
                    continue
                idv = row[idc - 1]
                if idv is None:
                    continue
                sid = str(idv).strip()
                if not sid:
                    continue
                hit = False
                for c in range(len(row)):
                    if c + 1 == idc:
                        continue
                    v = row[c]
                    if v is not None and str(v).strip() in changed_ids:
                        hit = True
                        break
                if hit:
                    related.setdefault(sid, (r, row))
            if not related:
                continue
            # 目标行索引（按调用ID）
            tgt_hdr, tgt_idc, tgt_ds = _probe(ws_tgt)
            tgt_rows = {}
            if tgt_hdr and tgt_idc and tgt_ds:
                for r, row in enumerate(ws_tgt.iter_rows(min_row=tgt_ds, values_only=True), start=tgt_ds):
                    if not row or len(row) < tgt_idc:
                        continue
                    v = row[tgt_idc - 1]
                    if v is not None:
                        tgt_rows.setdefault(str(v).strip(), r)
            sh_added = sh_updated = 0
            for sid in sorted(related):
                _, srow = related[sid]
                if sid in tgt_rows:
                    tr = tgt_rows[sid]
                    sh_updated += 1
                else:
                    tr = ws_tgt.max_row + 1
                    sh_added += 1
                # 按列位置整行复制
                for c, v in enumerate(srow, start=1):
                    if c - 1 < len(srow):
                        ws_tgt.cell(row=tr, column=c).value = v
            added += sh_added
            updated += sh_updated
            put(f"  {sn}: {sh_updated} 替换, {sh_added} 新增\n")
        if added + updated > 0:
            wb_tgt.save(tgt_path)
    except Exception as e:
        put(f"  同步索引表异常: {e}\n")
    finally:
        wb_src.close()
        wb_tgt.close()
    return added, updated
