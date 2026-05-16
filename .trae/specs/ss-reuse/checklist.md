# Checklist

## Task 1: `_parse_excel_lxml` 签名

- [x] `ss_values` 参数定义正确（Optional[List[str]] = None）
- [x] 非 None 时跳过 SS 解析，直接用传入值
- [x] None 时保持原逻辑（向后兼容）
- [x] `_parse_ss_values` 调用点不受影响

## Task 2: `_cmp_task_proc` 传入

- [x] `_zip_get_changed_sheets` 返回值扩展传 SS 值
- [x] cur_ss_values / prv_ss_values 正确传给 _parse_excel_lxml
- [x] 无 None 解引用风险（None 时 _parse_excel_lxml 走原路径）

## Task 3: 语法验证

- [x] `python -m py_compile` 通过

## Task 4: 行为验证

- [x] SS 复用时 _parse_excel_lxml 1.8s（省 lxml fromstring 1.1s）
- [x] 向后兼容验证通过
- [x] 8 diffs 结果不变
