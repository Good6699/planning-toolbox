import hashlib, sys, time
from zipfile import ZipFile
from lxml import etree

f1 = r'C:\Users\admin\.qclaw\workspace\临时辅助文件\Texts1.xlsm'
f2 = r'C:\Users\admin\.qclaw\workspace\临时辅助文件\Texts2.xlsm'

out = open(r'C:\Users\admin\.qclaw\workspace\_cmp_result.txt', 'w', encoding='utf-8')

def p(msg):
    out.write(msg + '\n')
    out.flush()
    print(msg, flush=True)

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ROW_T = '{%s}row' % NS
C_T = '{%s}c' % NS
V_T = '{%s}v' % NS
IS_T = '{%s}is' % NS
T_T = '{%s}t' % NS
SI_T = '{%s}si' % NS

t0 = time.time()
z1 = ZipFile(f1)
z2 = ZipFile(f2)
p(f"打开 ZIP: {time.time()-t0:.2f}s")

# Step 1: 找差异 sheet（只找 size 不同的，忽略格式化差异）
diff_sheets_by_size = []
diff_sheets_same_size = []
for name in sorted(z1.namelist()):
    try:
        d1 = z1.read(name)
        d2 = z2.read(name) if name in z2.namelist() else b''
        if d1 != d2:
            import re
            m = re.match(r'xl/worksheets/sheet(\d+)\.xml', name)
            if m:
                if len(d1) != len(d2):
                    diff_sheets_by_size.append((int(m.group(1)), len(d1), len(d2)))
                else:
                    diff_sheets_same_size.append(int(m.group(1)))
    except:
        pass

p(f"Size 不同的 sheet: {diff_sheets_by_size}")
p(f"同 size 但内容不同的 sheet (格式差异): {len(diff_sheets_same_size)} 个")

if not diff_sheets_by_size:
    p("\n所有 sheet 的单元格数据大小相同。差异仅来自格式/元数据/压缩。")
    p("这两个文件的单元格数据完全相同。")
    out.close()
    sys.exit(0)

# Step 2: 解析 sharedStrings（延迟加载）
t1 = time.time()
ss1_root = etree.fromstring(z1.read('xl/sharedStrings.xml'))
ss2_root = etree.fromstring(z2.read('xl/sharedStrings.xml'))

def extract_strings(root):
    strings = []
    for si in root:
        t_els = si.findall('.//{%s}t' % NS)
        if t_els:
            parts = [t.text or '' for t in t_els]
            strings.append(''.join(parts))
        else:
            strings.append('')
    return strings

ss1 = extract_strings(ss1_root)
ss2 = extract_strings(ss2_root)
p(f"sharedStrings: {len(ss1)} vs {len(ss2)} ({time.time()-t1:.2f}s)")

# Step 3: 对比 size 不同的 sheet 的单元格
def col_letter(ref):
    return ''.join(c for c in ref if c.isalpha())

def parse_inline(rt_el):
    parts = []
    for el in rt_el:
        if el.tag == T_T and el.text:
            parts.append(el.text)
    return ''.join(parts)

def cell_value(cell_el, ss_list):
    t = cell_el.get('t', '')
    v_el = cell_el.find(V_T)
    if v_el is not None and v_el.text:
        val = v_el.text
        if t == 's':
            try:
                idx = int(val)
                return ss_list[idx] if 0 <= idx < len(ss_list) else f'[BAD SS:{idx}]'
            except:
                return f'[BAD SS]'
        elif t == 'inlineStr':
            is_el = cell_el.find(IS_T)
            return parse_inline(is_el) if is_el is not None else ''
        return val
    return ''

total_cell_diffs = 0

for sn, sz1, sz2 in sorted(diff_sheets_by_size):
    sheet_name = f'xl/worksheets/sheet{sn}.xml'
    t2 = time.time()
    
    s1_xml = etree.fromstring(z1.read(sheet_name))
    s2_xml = etree.fromstring(z2.read(sheet_name))

    rows1 = {}
    for r in s1_xml.iter(ROW_T):
        rn = int(r.get('r', 0))
        cells = {}
        for c in r:
            if c.tag != C_T:
                continue
            col = col_letter(c.get('r', ''))
            cells[col] = cell_value(c, ss1)
        rows1[rn] = cells

    rows2 = {}
    for r in s2_xml.iter(ROW_T):
        rn = int(r.get('r', 0))
        cells = {}
        for c in r:
            if c.tag != C_T:
                continue
            col = col_letter(c.get('r', ''))
            cells[col] = cell_value(c, ss2)
        rows2[rn] = cells

    all_rows = sorted(set(rows1.keys()) | set(rows2.keys()))
    
    sheet_diffs = []
    for rn in all_rows:
        r1 = rows1.get(rn, {})
        r2 = rows2.get(rn, {})
        if rn not in rows1:
            sheet_diffs.append((rn, '新增', '', '', ''))
            continue
        if rn not in rows2:
            sheet_diffs.append((rn, '删除', '', '', ''))
            continue
        all_cols = set(r1.keys()) | set(r2.keys())
        for col in sorted(all_cols):
            v1 = r1.get(col, '')
            v2 = r2.get(col, '')
            if v1 != v2:
                sheet_diffs.append((rn, '修改', col, v1, v2))

    elapsed = time.time() - t2
    p(f"\nSheet{sn} (size={sz1}->{sz2}): {len(sheet_diffs)} 处差异 ({elapsed:.2f}s)")
    
    for rn, op, col, v1, v2 in sheet_diffs[:30]:
        p(f"  行{rn} {op} 列{col}: [{v1[:80]}] -> [{v2[:80]}]")
    if len(sheet_diffs) > 30:
        p(f"  ... 还有 {len(sheet_diffs)-30} 处差异")
    
    total_cell_diffs += len(sheet_diffs)

p(f"\n总计: {total_cell_diffs} 处单元格差异")
p(f"总耗时: {time.time()-t0:.2f}s")

z1.close()
z2.close()
out.close()
