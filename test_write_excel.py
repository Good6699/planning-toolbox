import os, sys

# 添加当前目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入函数
from svn_oneclick_compare import _load_cmp_file_settings, _get_cmp_config, write_excel

# 加载配置
_load_cmp_file_settings()

# 测试数据
results = [
    {"ID": "1", "::SC::": "测试1", "SubstituteId": "SUB1", "操作": "新增", "当前版本": "v1", "前一版本": "", "sheet": "Sheet1"},
    {"ID": "2", "::SC::": "测试2", "SubstituteId": "SUB2", "操作": "修改", "当前版本": "v1", "前一版本": "v0", "sheet": "Sheet1"},
    {"ID": "3", "::SC::": "测试3", "SubstituteId": "SUB3", "操作": "新增", "当前版本": "v1", "前一版本": "", "sheet": "Sheet2"},
    {"ID": "4", "::SC::": "测试4", "SubstituteId": "SUB4", "操作": "修改", "当前版本": "v1", "前一版本": "v0", "sheet": "Sheet2"},
]

# 测试文件
test_files = [
    "Text/Texts.xlsm",  # 应该匹配 Texts 配置，有输出列
    "OtherFile.xlsm",  # 应该使用默认配置，无输出列
]

for fname in test_files:
    print(f"\n测试文件: {fname}")
    tr, _, oc = _get_cmp_config(fname)
    print(f"title_rows: {tr}")
    print(f"output_cols: {oc}")
    print(f"output_cols is None: {oc is None}")
    
    # 生成输出文件路径
    out_file = f"test_{os.path.basename(fname)}"
    
    # 调用 write_excel 函数
    write_excel(results, out_file, oc, tr)
    print(f"已生成文件: {out_file}")
