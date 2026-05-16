"""
calamine 精度验证 — 独立脚本
对比 lxml 解析 vs calamine 逐单元格值
输出到文件: tools/calamine_verify_result.txt
"""
import sys, os, time, re
from io import BytesIO
from zipfile import ZipFile
from lxml import etree
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

_OUT = open(r'C:\Users\admin\.qclaw\workspace\tools\calamine_verify_result.txt', 'w', encoding='utf-8')
def log(msg=""):
    print(msg, flush=True)
    _OUT.write(msg + '\n')
    _OUT.flush()

from python_calamine import CalamineWorkbook

CACHE_DIR = r'C:\Users\admin\.qclaw\workspace\__byte_cache'
_XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_ROW_TAG = f"{{{_XML_NS}}}row"
_CELL_TAG = f"{{{_XML_NS}}}c"
_V_TAG = f"{{{_XML_NS}}}v"
_COL_RE = re.compile(r'^([A-Z]+)')
_MAX_ROWS = 3000  # 每 sheet 最多读 3000 行

def col_str(cell_ref):
    m = _COL_RE.match(cell_ref or "")
    return m.group(1) if m else ""

def parse_lxml_fast(raw_bytes, sheet_limit=5):
    """精简 lxml 解析"""
    zf = ZipFile(BytesIO(raw_bytes))

    shared_strings = []
    try:
        ss_xml = zf.read("xl/sharedStrings.xml")
        ss_root = etree.fromstring(ss_xml)
        for si in ss_root:
            t_els = si.findall(f".//{{{_XML_NS}}}t")
            shared_strings.append("".join(t.text or "" for t in t_els))
    except KeyError:
        pass

    wb_map = {}
    wb_xml = zf.read("xl/workbook.xml")
    wb_root = etree.fromstring(wb_xml)
    RELS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    sheet_map = {}
    for sh in wb_root.iter(f"{{{_XML_NS}}}sheet"):
        nm = sh.get("name", "")
        rid = sh.get(f"{{{RELS_NS}}}id", "")
        if nm and rid:
            sheet_map[nm] = rid
    rels = {}
    try:
        rels_xml = zf.read("xl/_rels/workbook.xml.rels")
        rels_root = etree.fromstring(rels_xml)
        for rel in rels_root:
            rels[rel.get("Id", "")] = rel.get("Target", "")
    except KeyError:
        pass
    for nm, rid in list(sheet_map.items())[:sheet_limit]:
        target = rels.get(rid, "")
        if target:
            wb_map[target] = nm

    result = {}
    for target, sname in wb_map.items():
        if not target.endswith(".xml"):
            target += ".xml"
        if not target.startswith("xl/"):
            target = "xl/" + target
        fh = zf.open(target)
        context = etree.iterparse(fh, events=('end',), tag=_ROW_TAG)

        sheet_rows = {}
        row_count = 0
        for ev, row in context:
            row_num = int(row.get("r", 0))
            if row_num == 1:
                row.clear()
                continue
            row_data = {}
            for cell in row:
                if cell.tag != _CELL_TAG:
                    continue
                col_l = col_str(cell.get("r", ""))
                t_attr = cell.get("t", "")
                v_el = cell.find(_V_TAG)
                val = ""
                if t_attr == "s" and v_el is not None and v_el.text:
                    try:
                        val = shared_strings[int(v_el.text)]
                    except (ValueError, IndexError):
                        val = ""
                elif v_el is not None and v_el.text:
                    val = v_el.text
                if col_l:
                    row_data[col_l] = val
            row.clear()
            sid = row_data.get('A', '')
            if sid:
                sheet_rows[sid] = row_data
                row_count += 1
                if row_count >= _MAX_ROWS:
                    break
        result[sname] = sheet_rows
    zf.close()
    return result

def col_letter(idx):
    i = idx
    r = []
    while True:
        r.append(chr(65 + i % 26))
        i = i // 26 - 1
        if i < 0:
            break
    return ''.join(reversed(r))

files = sorted(os.listdir(CACHE_DIR))[:1]

for bin_file in files:
    path = os.path.join(CACHE_DIR, bin_file)
    with open(path, 'rb') as f:
        raw = f.read()
    rev = int(bin_file.split('_')[1].replace('.bin', ''))
    log(f'\n{"="*70}')
    log(f'{bin_file}  (r{rev}, {len(raw)/1024/1024:.1f}MB)')

    log(f'lxml 解析中 (限 {_MAX_ROWS} 行/sheet, 前 5 sheet)...')
    t0 = time.time()
    lxml_all = parse_lxml_fast(raw, sheet_limit=5)
    t_lxml = time.time() - t0
    log(f'  lxml: {t_lxml:.2f}s, {sum(len(v) for v in lxml_all.values())} rows, {len(lxml_all)} sheets')

    log(f'calamine 解析中...')
    t0 = time.time()
    wb = CalamineWorkbook.from_filelike(BytesIO(raw))
    t_cal_load = time.time() - t0
    log(f'  calamine: {t_cal_load:.2f}s load, {len(wb.sheet_names)} sheets')

    total_cells = 0
    total_diff = 0
    all_diffs = []

    for sname in sorted(lxml_all.keys()):
        if sname not in wb.sheet_names:
            log(f'  [跳过] calamine 无 sheet: {sname}')
            continue
        lxml_rows = lxml_all[sname]
        cal_rows = wb.get_sheet_by_name(sname).to_python(skip_empty_area=False)

        if not cal_rows or len(cal_rows) < 2:
            continue

        cal_header = [str(v) if v is not None else '' for v in cal_rows[0]]
        sheet_diff = 0
        sheet_cells = 0

        for ri in range(1, min(len(cal_rows), _MAX_ROWS + 1)):
            row = cal_rows[ri]
            if not row:
                continue
            sid = str(row[0]) if row[0] is not None else ''
            if not sid or sid not in lxml_rows:
                continue
            lxml_data = lxml_rows[sid]

            for ci in range(1, min(len(cal_header), len(row))):
                cn = cal_header[ci]
                if not cn:
                    continue
                cal_l = col_letter(ci)
                lv = lxml_data.get(cal_l, '')
                cv = str(row[ci]) if row[ci] is not None else ''
                sheet_cells += 1
                if lv != cv:
                    sheet_diff += 1
                    total_diff += 1
                    if len(all_diffs) < 50:
                        all_diffs.append((sname, sid, cn, lv[:80], cv[:80]))

        total_cells += sheet_cells
        if sheet_diff == 0:
            log(f'  ✅ {sname}: {sheet_cells} cells, OK')
        else:
            log(f'  ❌ {sname}: {sheet_cells} cells, {sheet_diff} diffs')

    if total_diff == 0:
        log(f'\n✅ 结论: 完全一致, {total_cells} cells, 精度零损失')
    else:
        pct = total_diff / max(1, total_cells) * 100
        lxml_missing = sum(1 for d in all_diffs if d[3] == '')
        cal_missing = sum(1 for d in all_diffs if d[4] == '')
        ws_diff = sum(1 for d in all_diffs if d[3].strip() == d[4].strip())
        log(f'\n❌ {total_diff}/{total_cells} ({pct:.2f}%)')
        log(f'  lxml 缺值: {lxml_missing}')
        log(f'  calamine 缺值: {cal_missing}')
        log(f'  仅空白差异: {ws_diff}')
        log(f'  真实值差异: {total_diff - lxml_missing - cal_missing + ws_diff}')
        log(f'\n差异示例:')
        for sname, sid, cn, lv, cv in all_diffs[:15]:
            log(f'  [{sname}] id={sid} col={cn}')
            log(f'    lxml:     →{lv}←')
            log(f'    calamine: →{cv}←')
            log()

_OUT.close()
log(f'\n结果已保存到 tools/calamine_verify_result.txt')
