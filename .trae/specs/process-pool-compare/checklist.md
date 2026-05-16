# Checklist

## Task 1: 提取 `_zip_get_changed_sheets` 到模块顶层

- [x] 函数定义在 `step3_download_and_compare` 之外（模块顶层 L1910）
- [x] `step3_download_and_compare` 内部无 `_zip_get_changed_sheets` 定义
- [x] 闭包引用 `io`、`zipfile`、`_SHEET_ENTRY_RE` 在模块顶层可访问
- [x] Phase 2 内调用自动指向模块级函数名

## Task 2: 提取 `_cmp_task` 到模块顶层

- [x] 函数定义为 `_cmp_task_proc(args: tuple)`，模块顶层
- [x] 内部解包 `cur_b, prv_b, cur, prv, fname = args`
- [x] 逻辑与改造前完全一致（ZIP预检→跳过/解析→对比→返回结果元组）
- [x] `_parse_excel_lxml` / `_compare_pair` / `_get_cmp_config` 在子进程中可正常调用
- [x] 模块级 `_load_cmp_file_settings()` 调用确保 spawn 子进程有完整配置

## Task 3: Phase 2 改用 ProcessPoolExecutor

- [x] `ProcessPoolExecutor` 替代 `ThreadPoolExecutor`
- [x] `max_workers = min(expected_pairs, os.cpu_count())`
- [x] 提交格式 `ex.submit(_cmp_task_proc, (cur_b, prv_b, cur, prv, fname))`
- [x] `as_completed` 收集结果与改造前一致
- [x] workbook 轻量解析仍在主进程执行（Phase 2 并行前）

## Task 4: 语法验证

- [x] `python -m py_compile svn_oneclick_compare.py` 无错误
- [x] `graphify update` 执行成功

## Task 5: 行为验证

- [x] `_zip_get_changed_sheets` → `({"sheet27"}, True)` ✓
- [x] `_parse_excel_lxml` + `_compare_pair` 直接调用 → 4 条差异 ✓
- [x] `_cmp_task_proc("Texts.xlsm")` → 4 条差异，id_col 正确 ✓
