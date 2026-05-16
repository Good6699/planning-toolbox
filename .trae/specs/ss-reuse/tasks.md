# Tasks

- [x] Task 1: `_parse_excel_lxml` 新增 `ss_values` 参数
  - [x] 1.1 签名加 `ss_values: Optional[List[str]] = None`
  - [x] 1.2 非 None 时跳过 SS 解析，直接用传入值
  - [x] 1.3 None 时保持原逻辑不变

- [x] Task 2: `_cmp_task_proc` 传入 SS 值
  - [x] 2.1 `_zip_get_changed_sheets` 返回值扩展为 `(changed, ss_changed, cur_ss_values, prv_ss_values)`
  - [x] 2.2 调用 `_parse_excel_lxml` 时传入 `ss_values`

- [x] Task 3: 语法验证
  - [x] `python -m py_compile` 通过

- [x] Task 4: 行为验证
  - [x] SS 复用时 _parse_excel_lxml 1.8s（vs 2.1s 不复用）
  - [x] 向后兼容：不传 ss_values 仍正常工作
  - [x] _cmp_task_proc: 8 diffs, 6.5s ✓

# Task Dependencies
- Task 1 独立
- Task 2 依赖 Task 1
- Task 3 依赖 Task 2
- Task 4 依赖 Task 2
