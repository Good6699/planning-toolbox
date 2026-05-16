# Tasks

- [x] Task 1: `_parse_excel_lxml` 新增 `only_sheets` 参数
  - [x] 1.1 函数签名增加 `only_sheets: Optional[set] = None`
  - [x] 1.2 在 `for target, sheet_name in wb_map.items():` 循环开头，增加跳过逻辑：用 `_SHEET_ENTRY_RE.search(target)` 匹配 sheet 编号
  - [x] 1.3 确认 `result["_sheet_order"]` 由 `list(result["sheets"].keys())` 自动反映只解析的 sheet
  - [x] 1.4 确认 `result["_header_data"]` 也只包含解析过的 sheet（与 `result["sheets"]` 一致）

- [x] Task 2: `_parse_excel_with_cache` 透传 `only_sheets`，缓存 key 包含指纹
  - [x] 2.1 函数签名增加 `only_sheets: Optional[set] = None`
  - [x] 2.2 缓存 key 构建：当 `only_sheets` 不为 None 时，追加 `_sheets:` + `,`.join(sorted(only_sheets))
  - [x] 2.3 `only_sheets=None` 时缓存 key 与改造前完全一致（向后兼容旧 pickle 缓存）— 验证：`237f3012..._1_B`
  - [x] 2.4 调用 `_parse_excel_lxml` 时透传 `only_sheets=only_sheets`

- [x] Task 3: Phase 2 并行前获取完整 sheet_order（workbook 轻量解析）
  - [x] 3.1 在 Phase 2 并行循环之前，新增轻量 workbook 解析：从首个可用文件字节读取 workbook.xml，用 lxml 解析全部 sheet 名称
  - [x] 3.2 解析失败时回退到运行时收集（`fname not in full_sheet_order and not file_sheet_order.get(fname)`）

- [x] Task 4: `_cmp_task` 传递 `only_sheets`
  - [x] 4.1 `changed_sheets` 非空时作为 `only_sheets` 传递
  - [x] 4.2 `changed_sheets` 为空 + `ss_changed=False` 时保留跳过逻辑（直接返回 `[]`）
  - [x] 4.3 `changed_sheets` 为空 + `ss_changed=True` 时传 `only_sheets=None`（全量解析）

- [x] Task 5: 语法验证 + graphify update
  - [x] 5.1 `python -m py_compile svn_oneclick_compare.py` 通过
  - [x] 5.2 `graphify update` 执行成功

- [x] Task 6: 行为验证
  - [x] 6.1 用 Texts1 手动调用 `only_sheets={"sheet27"}`：解析 1 个 sheet（String_3_各种提示3），8530 行，耗时 1.06-1.24s
  - [x] 6.2 `_compare_pair` 对部分解析结果正确处理：4 条差异（与 `quick_excel_diff.py` 完全一致）
  - [x] 6.3 差异行内容：修改×3 + 新增×1，与已知结果一致
  - [x] 6.4 workbook 轻量解析：58 个 sheet 全部获取

# Task Dependencies
- Task 1 独立
- Task 2 依赖 Task 1
- Task 3 独立
- Task 4 依赖 Task 2
- Task 5 依赖 Task 1-4
- Task 6 依赖 Task 1-4
