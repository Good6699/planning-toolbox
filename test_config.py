import os, json

# 检查配置文件是否存在
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svn_gui_config.json")
print(f"配置文件路径: {config_file}")
print(f"文件是否存在: {os.path.isfile(config_file)}")

# 尝试读取配置文件
if os.path.isfile(config_file):
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        print(f"配置文件内容: {cfg}")
        print(f"cmp_file_settings: {cfg.get('cmp_file_settings', {})}")
    except Exception as e:
        print(f"读取配置文件失败: {e}")
else:
    print("配置文件不存在，创建一个示例配置文件")
    # 创建示例配置文件
    sample_config = {
        "cmp_title_rows": "1",
        "cmp_id_col": "::ID::",
        "cmp_global_id_col": "",
        "cmp_output_cols": "",
        "cmp_file_settings": {
            "Texts": {
                "cmp_title_rows": "1",
                "cmp_id_col": "::ID::",
                "cmp_global_id_col": "",
                "cmp_output_cols": ""
            }
        }
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(sample_config, f, indent=2, ensure_ascii=False)
    print("示例配置文件已创建")
