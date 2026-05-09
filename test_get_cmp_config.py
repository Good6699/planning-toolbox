import os, sys

# 添加当前目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入函数
from svn_oneclick_compare import _load_cmp_file_settings, _get_cmp_config, _CMP_FILE_SETTINGS

# 加载配置
_load_cmp_file_settings()
print(f"_CMP_FILE_SETTINGS: {_CMP_FILE_SETTINGS}")

# 测试 _get_cmp_config 函数
test_files = [
    "Text/Texts.xlsm",  # 应该匹配 Texts 配置
    "OtherFile.xlsm",  # 应该使用默认配置
]

for fname in test_files:
    tr, ic, oc = _get_cmp_config(fname)
    print(f"\n文件: {fname}")
    print(f"title_rows: {tr}")
    print(f"id_col: {ic}")
    print(f"output_cols: {oc}")
    print(f"output_cols is None: {oc is None}")
