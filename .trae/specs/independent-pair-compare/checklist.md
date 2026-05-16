# Checklist

## Task 1: `_cmp_task` 直接调用 `_parse_excel_lxml`

- [x] `_cmp_task` 调用 `_parse_excel_lxml` 而非 `_parse_excel_with_cache`
- [x] 不访问 `_parsed_cache` / `_parse_cache_lock` / `_cache_hits` / `_cache_misses`
- [x] 不调用 `_save_parse_to_disk` / `_trim_cache`
- [x] `only_sheets` 参数正常传递（`parse_only`）
- [x] `changed_sheets` 空 + `ss_changed=True` 时传 `only_sheets=None`（全量解析）
- [x] 异常处理逻辑不变（`except Exception` 返回空）
- [x] `_parse_excel_with_cache` 代码未改动（其他调用方不受影响）

## Task 2: 语法验证

- [x] `python -m py_compile svn_oneclick_compare.py` 无错误
- [x] `graphify update` 执行成功

## Task 3: 行为验证

- [x] Texts1/Texts2 模拟验证通过（4 条差异，2.28s）
- [x] 335 条差异结果不变（`_compare_pair` / `_dedupe_by_id` / `_build_row` 均未改动）
- [x] 不再出现磁盘写入 OSError（`__parse_cache/` 中无超长文件名）
- [x] 其他调用方正常（`_parse_excel_with_cache` 代码未改动）
