# Checklist

- [x] `_compute_sheet_content_fingerprint` 函数已新增，正确提取 cell ref+v 并拼接 MD5
- [x] `_regex_scan_structure` 返回 `(struct_dict, ss_crc)`，ss_crc 正确从 ZIP 读取
- [x] `_sheet_fp_cache` 已替换为 `_sheet_content_fp_cache`，所有引用处已更新
- [x] `_process_one_pair` 中 Phase B 使用内容指纹比较，保留 sheet 跳过逻辑
- [x] `_compare_pair` 中 `_hash` 字段是否使用已确认，无用引用已清理
- [x] 语法验证通过（`python -m py_compile`）
- [x] graphify update 执行通过
