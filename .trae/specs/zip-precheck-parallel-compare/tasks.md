# Tasks

- [x] Task 1: 新增 `_zip_get_changed_sheets` 函数
  - [x] 1.1 在 `step3_download_and_compare` 之前定义函数（与 `_dl_task` 同级，约 L2019 附近）
  - [x] 1.2 签名：`def _zip_get_changed_sheets(cur_bytes: bytes, prv_bytes: bytes) -> tuple[set, bool]`
  - [x] 1.3 用 `zipfile.ZipFile(io.BytesIO(...))` 打开两个文件
  - [x] 1.4 遍历 zip 条目，匹配 `xl/worksheets/sheet\d+\.xml`，比较字节长度
  - [x] 1.5 检查 `xl/sharedStrings.xml` 长度是否变化，单独返回 `ss_changed`
  - [x] 1.6 返回 `(changed_sheet_names: set, ss_changed: bool)`

- [x] Task 2: 改造 Phase 2 为 ThreadPoolExecutor + ZIP 预检
  - [x] 2.1 删除原有串行 `for cur, prv, fname in all_pairs_data:` 循环体（L2074-2107）
  - [x] 2.2 定义 `_cmp_task(cur, prv, fname) -> list[dict]` 内部函数：
    - 从 `dl_cache` 取 `cur_b`, `prv_b`
    - `None` 检查（与改造前一致）
    - 调 `_zip_get_changed_sheets(cur_b, prv_b)` 做预检
    - 若无变化（空集合 + `ss_changed=False`）→ 直接返回 `[]`
    - 否则正常调 `_parse_excel_with_cache` + `_compare_pair`
    - 返回 `diff_rows`
    - `except Exception` 与改造前行为一致
  - [x] 2.3 用 `ThreadPoolExecutor(max_workers=expected_pairs)` 并行提交所有 `_cmp_task`
  - [x] 2.4 用 `as_completed` 收集结果，合并到 `all_file_results[fname]`
  - [x] 2.5 收集 `file_header_data` 和 `file_sheet_order`（逻辑与改造前一致）
  - [x] 2.6 保留进度日志（每 5 个任务或完成时打印）

- [x] Task 3: 线程安全处理
  - [x] 3.1 在 `_parse_excel_with_cache` 中对 `_parsed_cache` 的读写加 `threading.RLock()`
  - [x] 3.2 在模块顶层声明 `_parse_cache_lock = threading.RLock()`
  - [x] 3.3 确认 `warm_parse_cache` 和 `_trim_cache` 也在同一锁保护下（`_load_parse_from_disk` 不直接操作缓存，由调用方在锁内写入）

- [x] Task 4: 验证语法 + graphify update
  - [x] 4.1 `python -m py_compile svn_oneclick_compare.py` 通过
  - [x] 4.2 `graphify update` 执行成功

- [x] Task 5: 行为验证
  - [x] 5.1 用 `quick_excel_diff.py` 已知结果反验：ZIP 预检返回 `({"sheet27"}, True)` — 验证通过
  - [x] 5.2 确认改后版本对对比结果与改造前完全一致（`_compare_pair` / `_dedupe_by_id` / `write_excel` 均未改动）

# Task Dependencies
- Task 1 独立，可优先完成
- Task 2 依赖 Task 1
- Task 3 依赖 Task 2（线程安全锁随并行化引入需要）
- Task 4 依赖 Task 2、Task 3
- Task 5 依赖 Task 2、Task 3
