# Checklist

- [x] `_ss_crc_cache` 全局缓存已新增，Phase A 正确缓存 sharedStrings CRC
- [x] Phase B 使用 ZIP CRC32 判定 sheet 变化：`sd["crc"]` 比较
- [x] Phase B 使用 `_ss_crc_cache` 判定 sharedStrings 变化，变化时标记所有 sheet
- [x] 全部跳过时"0 条差异"日志正确输出
- [x] `_compute_sheet_content_fingerprint` 已删除
- [x] `_sheet_content_fp_cache` 已删除，无残留引用
- [x] 语法验证通过（`python -m py_compile`）
- [x] graphify update 执行通过
