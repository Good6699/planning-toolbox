# Smart Sheet Parsing Spec

## Why
ZIP 预检已精确识别出 size 变化的 sheet（如 sheet27 变了，其余 57 个没变），但 `_parse_excel_lxml` 仍然全量解析 58 个 sheet。单文件解析 13s，32 对 × 2 文件 × (1-缓存命中率) 成为硬瓶颈。生产数据中 sharedStrings 每个版本都变 → ZIP 预检无法跳过任何版本对 → 49 次全量解析 = 637s 硬下限。

`quick_excel_diff.py` 验证了方案：只解析变化的 sheet → ~0.3s/文件。将此能力传入 `_parse_excel_lxml`，解析时间从 13s → ~0.3s/文件（49 次 ≈ 15s），总耗时从 ~1200s → ~100s。

同时解决 `_sheet_order` 不完整问题：`only_sheets` 会导致未解析 sheet 不出现在 sheet 顺序列表中。

## What Changes
- `_parse_excel_lxml` 新增 `only_sheets: Optional[set] = None` 参数，只解析指定 sheet
- `_parse_excel_with_cache` 透传 `only_sheets`，缓存 key 包含 `only_sheets` 指纹
- `_cmp_task` 将 ZIP 预检的 `changed_sheets` 传给 `_parse_excel_with_cache`
- Phase 2 并行循环前，从第一个可用文件字节中轻量解析 workbook.xml 获取完整 sheet_order，修复 `_sheet_order` 不完整问题
- `_parse_excel_lxml` 中 `only_sheets` 内部逻辑：遍历 `wb_map` 时跳过 `sheet_name not in only_sheets` 的 sheet
- 不改 `_compare_pair` / `_compare_pair_merge` / `_dedupe_by_id` / `write_excel`

## Impact
- Affected specs: `zip-precheck-parallel-compare`（在其基础上进一步优化）
- Affected code: `svn_oneclick_compare.py` — `_parse_excel_lxml`, `_parse_excel_with_cache`, `_cmp_task`, Phase 2 前新增 workbook 轻量解析

## ADDED Requirements

### Requirement: `_parse_excel_lxml` 按需解析
系统 SHALL 支持通过 `only_sheets` 参数指定只解析部分 sheet，未指定的 sheet 不出现在返回的 `sheets` 和 `map` 中。

#### Scenario: 指定 only_sheets
- **WHEN** `only_sheets={"sheet27"}` 传入
- **THEN** 只解析 workbook 中名为 "sheet27" 的 sheet
- **AND** `result["sheets"]` 只包含 "sheet27"
- **AND** `result["map"]` 只包含 sheet27 的行
- **AND** `result["_sheet_order"]` 为 `["sheet27"]`

#### Scenario: only_sheets=None 全量解析
- **WHEN** `only_sheets` 为 None 或不传
- **THEN** 行为与改造前完全一致：解析所有 sheet
- **AND** `result["sheets"]` 包含全部 sheet
- **AND** `result["_sheet_order"]` 包含全部 sheet 顺序

#### Scenario: sharedStrings 始终解析
- **WHEN** `only_sheets` 指定了 sheet 子集
- **THEN** sharedStrings.xml 仍正常解析（cell 的 t="s" 引用需要它）
- **AND** sharedStrings 的 CRC 缓存机制不变

#### Scenario: global_id_col 发现
- **WHEN** `only_sheets` 的第一个 sheet 不是原始第一个 sheet
- **THEN** `global_id_col` 从 `only_sheets` 中第一个（按 workbook 顺序）解析的 sheet 中发现
- **AND** 后续同一个 `only_sheets` 中的 sheet 复用该 `global_id_col`

### Requirement: 缓存 key 包含 only_sheets 指纹
解析缓存 key SHALL 包含 `only_sheets` 信息，以区分同一文件的不同部分解析结果。

#### Scenario: 同文件不同 only_sheets 不同缓存
- **WHEN** 同一 raw_bytes 分别以 `only_sheets={"sheet27"}` 和 `only_sheets={"sheet30"}` 解析
- **THEN** 两次解析使用不同的缓存 key
- **AND** 不会命中对方的缓存

#### Scenario: only_sheets=None 向后兼容
- **WHEN** `only_sheets=None`
- **THEN** 缓存 key 与改造前完全一致
- **AND** 旧的 pickle 缓存仍可命中

### Requirement: Phase 2 并行前获取完整 sheet_order
Phase 2 SHALL 在并行循环前通过轻量解析 workbook.xml 获取完整的 sheet 顺序，以修复 `only_sheets` 导致的 `_sheet_order` 不完整问题。

#### Scenario: 从第一个可用文件获取完整顺序
- **WHEN** Phase 2 并行开始前
- **THEN** 从 `all_pairs_data` 中第一个文件字节轻量解析 workbook.xml
- **AND** 如有多个文件，按第一个文件字节获取
- **AND** 获得的完整 sheet_order 用于最终 `file_sheet_order`
- **AND** 如果所有文件字节都不可用，回退到运行时收集的 `_sheet_order`

## MODIFIED Requirements
无。

## REMOVED Requirements
无。
