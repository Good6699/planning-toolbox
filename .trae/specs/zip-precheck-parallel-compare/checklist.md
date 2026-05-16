# Checklist

## Task 1: 新增 `_zip_get_changed_sheets` 函数

- [x] 函数使用 `io.BytesIO` + `zipfile.ZipFile`，不落磁盘
- [x] 正则 `xl/worksheets/sheet(\d+)\.xml` 正确匹配所有 sheet 条目
- [x] 比较的是 `len(data)`（字节长度），不是 CRC/MD5
- [x] 返回值只包含 **size 不同** 的 sheet（同 size 不同内容的不放入）
- [x] `xl/sharedStrings.xml` 大小变化单独返回 `ss_changed`
- [x] 两文件 sheet 集合不同时（新增/删除 sheet），缺失方的 sheet 视为 size=-1，加入变化集合
- [x] 函数有 try/except 保护，任何异常返回 `(set(), False)`，不阻断主流程
- [x] 闭包两个 ZipFile（`with ZipFile(...) as z1, ZipFile(...) as z2:`）

## Task 2: Phase 2 ThreadPoolExecutor 改造

- [x] `_cmp_task` 内部函数逻辑完整：取 bytes → 预检 → 跳过 or 解析+对比 → 返回 diff
- [x] `cur_b`/`prv_b` 为 None 时行为与改造前一致（continue 跳过 → 返回空 diff）
- [x] ZIP 预检判定"无变化"时直接返回 `[]`，不调用 `_parse_excel_with_cache`
- [x] 有变化时正常调用 `_parse_excel_with_cache` + `_compare_pair`，传参与改造前一致
- [x] `ThreadPoolExecutor(max_workers=expected_pairs)` 提交所有任务
- [x] `as_completed` 收集结果：`all_file_results[fname].extend(diff_rows)`
- [x] `file_header_data` 和 `file_sheet_order` 收集逻辑与改造前一致
- [x] 进度日志保留（约每 5 个完成时打印）
- [x] 异常 catch 逻辑保留（单个对出错不影响其他）

## Task 3: 线程安全

- [x] 模块顶层声明 `_parse_cache_lock = threading.RLock()`（用 RLock 避免 `_trim_cache` 重入死锁）
- [x] `_parse_excel_with_cache` 中所有 `_parsed_cache` 读/写操作在 `with _parse_cache_lock:` 下
- [x] `warm_parse_cache` 中遍历 `_parsed_cache` 时也在锁保护下
- [x] `_load_parse_from_disk` 不直接操作 `_parsed_cache`，由调用方在锁内完成写入
- [x] 全局变量 `_cache_hits`/`_cache_misses` 的累加在锁保护下

## Task 4: 语法验证

- [x] `python -m py_compile svn_oneclick_compare.py` 无错误
- [x] `graphify update` 执行成功

## Task 5: 行为验证

- [x] 用已知数据验证 `_zip_get_changed_sheets` 返回结果正确：`sheet27` + `ss_changed=True`
- [x] 确认对比结果（差异行数量、每条差异的内容）与改造前完全一致（`_compare_pair` 调用方式不变）
- [x] 确认输出 Excel 格式无变化（`write_excel` 未改动）
- [x] 确认 `_dedupe_by_id` 后结果无变化（`_dedupe_by_id` 未改动）
