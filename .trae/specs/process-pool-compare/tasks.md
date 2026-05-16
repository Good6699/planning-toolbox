# Tasks

- [x] Task 1: 提取 `_zip_get_changed_sheets` 到模块顶层
  - [x] 1.1 从 `step3_download_and_compare` 闭包中取出函数体，放到模块顶层（L1910 之后）
  - [x] 1.2 签名：`def _zip_get_changed_sheets(cur_bytes: bytes, prv_bytes: bytes) -> tuple[set, bool]`
  - [x] 1.3 移除 `step3_download_and_compare` 内部的 `_zip_get_changed_sheets` 定义
  - [x] 1.4 Phase 2 中调用已自动指向模块级函数

- [x] Task 2: 提取 `_cmp_task` 到模块顶层
  - [x] 2.1 从 `step3_download_and_compare` 闭包中取出函数体，放到模块顶层
  - [x] 2.2 签名改为接收单一元组参数：`def _cmp_task_proc(args: tuple) -> tuple`
  - [x] 2.3 `args = (cur_b, prv_b, cur, prv, fname)`，解包后逻辑不变
  - [x] 2.4 移除 `step3_download_and_compare` 内部的 `_cmp_task` 定义
  - [x] 2.5 `_get_cmp_config` / `_parse_excel_lxml` / `_compare_pair` 均为模块级函数，spawn 子进程可直接调用
  - [x] 2.6 添加模块级 `_load_cmp_file_settings()` 调用，确保子进程加载配置

- [x] Task 3: Phase 2 改用 ProcessPoolExecutor
  - [x] 3.1 导入 `from concurrent.futures import ProcessPoolExecutor`
  - [x] 3.2 `max_workers = min(expected_pairs, os.cpu_count())`
  - [x] 3.3 `ProcessPoolExecutor(max_workers=proc_workers)` 替代 `ThreadPoolExecutor`
  - [x] 3.4 提交时打包参数：`ex.submit(_cmp_task_proc, (dl_cache.get(...), dl_cache.get(...), cur, prv, fname))`
  - [x] 3.5 `as_completed` 收集结果逻辑不变

- [x] Task 4: 语法验证 + graphify update
  - [x] 4.1 `python -m py_compile svn_oneclick_compare.py` 通过
  - [x] 4.2 `graphify update` 执行成功

- [x] Task 5: 行为验证
  - [x] 5.1 `_zip_get_changed_sheets` 直接调用 → `({"sheet27"}, True)` ✓
  - [x] 5.2 `_parse_excel_lxml + _compare_pair` 直接调用 → 4 条差异，2.6s ✓
  - [x] 5.3 `_cmp_task_proc("Texts.xlsm")` → 4 条差异，1.7s，id_col=::ID:: ✓

# Task Dependencies
- Task 1 独立
- Task 2 独立
- Task 3 依赖 Task 1、Task 2
- Task 4 依赖 Task 3
- Task 5 依赖 Task 3
