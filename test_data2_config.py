import os, sys

# 添加当前目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入函数
from svn_oneclick_compare import _load_cmp_file_settings, _get_cmp_config

# 加载配置
_load_cmp_file_settings()

# 测试 Data2 文件
fname = "Data2.xlsm"
print(f"测试文件: {fname}")
tr, ic, oc = _get_cmp_config(fname)
print(f"title_rows: {tr}")
print(f"id_col: {ic}")
print(f"output_cols: {oc}")
print(f"output_cols is None: {oc is None}")

# 测试完整路径
fname_full = "路径/Data2.xlsm"
print(f"\n测试完整路径: {fname_full}")
tr, ic, oc = _get_cmp_config(fname_full)
print(f"title_rows: {tr}")
print(f"id_col: {ic}")
print(f"output_cols: {oc}")
print(f"output_cols is None: {oc is None}")
