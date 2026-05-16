# Checklist

## Task 1: `_parse_excel_lxml` 新增 `only_sheets` 参数

- [x] 函数签名增加了 `only_sheets: Optional[set] = None`
- [x] `for target, sheet_name in wb_map.items():` 循环内有跳过逻辑（`_SHEET_ENTRY_RE.search(target)`）
- [x] `only_sheets=None` 时行为与改造前完全一致
- [x] `only_sheets={"sheet27"}` 时只解析 sheet27（实际：String_3_各种提示3），其余 sheet 不出现在结果中
- [x] sharedStrings 解析不受影响（始终解析，不依赖 only_sheets）
- [x] `global_id_col` 发现逻辑在 `only_sheets` 场景下正常工作
- [x] `result["_header_data"]` 只包含解析过的 sheet
- [x] `_hash` 计算只对解析过的 sheet 执行

## Task 2: `_parse_excel_with_cache` 透传

- [x] 函数签名增加了 `only_sheets: Optional[set] = None`
- [x] `only_sheets=None` 时缓存 key 完全与改造前一致（`237f3012..._1_B`）
- [x] `only_sheets={"sheet27"}` 时缓存 key 包含 `_sheets_sheet27`
- [x] `only_sheets` 相同但顺序不同的集合产生相同缓存 key（sorted）
- [x] `_parse_excel_lxml` 调用透传了 `only_sheets=only_sheets`

## Task 3: Phase 2 完整 sheet_order

- [x] Phase 2 并行循环前有 workbook 轻量解析（58 个 sheet 全部获取）
- [x] 使用 `zipfile.ZipFile(io.BytesIO(...))` 不落磁盘
- [x] 解析失败时有 try/except 兜底，回退到运行时收集

## Task 4: `_cmp_task` 传递 `only_sheets`

- [x] `changed_sheets` 非空时作为 `only_sheets` 传递
- [x] `changed_sheets` 为空 + `ss_changed=False` 时直接返回 `[]`（现有逻辑）
- [x] `changed_sheets` 为空 + `ss_changed=True` 时传 `only_sheets=None`（全量解析）

## Task 5: 语法验证

- [x] `python -m py_compile svn_oneclick_compare.py` 无错误
- [x] `graphify update` 执行成功

## Task 6: 行为验证

- [x] `only_sheets={"sheet27"}` 解析结果只包含 1 个 sheet，8530 行，耗时 1.06-1.24s
- [x] 差异行数 4 条，与 `_cmp_result.txt` 一致
- [x] 每条差异的内容正确（修改×3 + 新增×1）
- [x] 输出 Excel 格式无变化（`_compare_pair` / `_build_row` / `write_excel` 均未改动）
