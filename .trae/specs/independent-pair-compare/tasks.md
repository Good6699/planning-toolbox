# Tasks

- [x] Task 1: `_cmp_task` 改为直接调用 `_parse_excel_lxml`
  - [x] 1.1 `_parse_excel_with_cache` → `_parse_excel_lxml` (cur + prv，各 1 行)
  - [x] 1.2 prv 同理
  - [x] 1.3 `if not cur_parsed or not prv_parsed` 逻辑不变
  - [x] 1.4 不引入 `_parsed_cache` / `_parse_cache_lock` / `_save_parse_to_disk` 依赖

- [x] Task 2: 语法验证 + graphify update
  - [x] 2.1 `python -m py_compile svn_oneclick_compare.py` 通过
  - [x] 2.2 `graphify update` 执行成功

- [x] Task 3: 行为验证
  - [x] 3.1 Texts1/Texts2 模拟验证：4 条差异，2.28s
  - [x] 3.2 差异内容：修改×3 + 新增×1，与改造前一致
  - [x] 3.3 `__parse_cache/` 中无超长文件名，确认不会 OSError
  - [x] 3.4 `_parse_excel_with_cache` 代码未改动，其他调用方不受影响

# Task Dependencies
- Task 1 独立
- Task 2 依赖 Task 1
- Task 3 依赖 Task 1
