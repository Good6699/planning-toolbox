import sys
sys.path.insert(0, r'C:\Users\admin\.qclaw\workspace')
from svn_oneclick_compare import _parse_excel_lxml, _normalize_value

# 读取两个版本
file1 = r'C:\Users\admin\AppData\Local\Temp\svn_cache_1_b3cb1b\temp_339655.xlsm'
file2 = r'C:\Users\admin\AppData\Local\Temp\svn_cache_1_b3cb1b\temp_339620.xlsm'

with open(file1, 'rb') as f:
    data1 = f.read()
with open(file2, 'rb') as f:
    data2 = f.read()

p1 = _parse_excel_lxml(data1, 339655, title_rows=1, id_col='::ID::')
p2 = _parse_excel_lxml(data2, 339620, title_rows=1, id_col='::ID::')

# 查找 yinyong000004369
sid = 'yinyong000004369'
if p1 and sid in p1['map']:
    info1 = p1['map'][sid]
    print('=== 版本 339655 ===')
    print(f'SC: {info1.get("sc", "")}')
    print(f'SC normalized: {_normalize_value(info1.get("sc", ""))}')
    cells1 = info1.get('cells', {})
    for k, v in sorted(cells1.items()):
        print(f'{k}: {repr(v)} -> {repr(_normalize_value(str(v)))}')

if p2 and sid in p2['map']:
    info2 = p2['map'][sid]
    print('\n=== 版本 339620 ===')
    print(f'SC: {info2.get("sc", "")}')
    print(f'SC normalized: {_normalize_value(info2.get("sc", ""))}')
    cells2 = info2.get('cells', {})
    for k, v in sorted(cells2.items()):
        print(f'{k}: {repr(v)} -> {repr(_normalize_value(str(v)))}')

# 对比差异
if p1 and p2 and sid in p1['map'] and sid in p2['map']:
    cells1 = p1['map'][sid].get('cells', {})
    cells2 = p2['map'][sid].get('cells', {})
    print('\n=== 规范化后对比 ===')
    all_keys = set(cells1.keys()) | set(cells2.keys())
    has_diff = False
    for k in sorted(all_keys):
        v1 = cells1.get(k, '')
        v2 = cells2.get(k, '')
        nv1 = _normalize_value(str(v1)) if v1 is not None else ""
        nv2 = _normalize_value(str(v2)) if v2 is not None else ""
        if nv1 != nv2:
            has_diff = True
            print(f'{k}: {repr(nv1)} != {repr(nv2)}')
    if not has_diff:
        print('无差异')
