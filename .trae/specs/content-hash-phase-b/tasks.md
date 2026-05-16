# Tasks

- [x] Task 1: 新增 `_compute_sheet_content_fingerprint` 函数
  - 紧接 `_compute_sheet_fingerprint` 之后（~L929）
  - 提取 sheet XML 中所有 cell ref+v → 排序拼接 → MD5(数据+"|ss:"+SS_CRC)
  - 返回 32 字符 hex 字符串

- [x] Task 2: 修改 `_regex_scan_structure` 返回 ss_crc
  - 从 ZIP 读取 `xl/sharedStrings.xml` 的 CRC
  - 返回值从 `-> Optional[Dict[str, dict]]` 改为 `-> Tuple[Optional[Dict[str, dict]], int]`

- [x] Task 3: 全局缓存 `_sheet_fp_cache` → `_sheet_content_fp_cache`
  - 全局声明处改名
  - `_process_one_pair` 中所有引用处改名
  - `_compute_sheet_fingerprint` 调用替换为 `_compute_sheet_content_fingerprint`

- [x] Task 4: 修改 `_process_one_pair` 中 Phase B 逻辑
  - Phase A 缓存路径：`_regex_scan_structure` 调用解包 ss_crc
  - Phase B 比较：用 `_sheet_content_fp_cache` 中的内容指纹判断变化 sheet
  - 清理 `_structure_cache` 中不再需要的 `_hash` 字段引用

- [x] Task 5: 验证语法 + graphify update
  - `python -m py_compile` 验证语法
  - `graphify update` 更新知识图谱

# Task Dependencies

无（可串行执行）
