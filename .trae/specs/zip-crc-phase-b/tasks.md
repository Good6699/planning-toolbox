# Tasks

- [x] Task 1: `_regex_scan_structure` 恢复缓存 ss_crc
  - zip 文件级别加到 `_structure_cache`（新增 `_ss_crc_cache: Dict[str, int]`）
  - Phase A 缓存时将 ss_crc 存入 `_ss_crc_cache[content_hash]`

- [x] Task 2: Phase B 改为 ZIP CRC32 比较
  - sheet 变化判定：`sd["crc"]` 是否相等
  - sharedStrings CRC 变化判定：`_ss_crc_cache[cur_ch] != _ss_crc_cache[prv_ch]`
  - SS 变化 → 标记所有 sheet 为变化（原样返回 `all_sn` 作为 `changed_sheets`）

- [x] Task 3: 清理 `_compute_sheet_content_fingerprint` 和 `_sheet_content_fp_cache`
  - 删除函数
  - 删除全局缓存声明
  - 删除 Phase A 中写入缓存的代码

- [x] Task 4: 验证语法 + graphify update

# Task Dependencies

无
