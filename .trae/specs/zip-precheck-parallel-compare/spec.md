# ZIP 预检 + 并行对比 Spec

## Why
当前 Phase 2 对比是串行 for 循环，对每个版本对都要全量 lxml iterparse 解析两份 Excel，然后才调用 `_compare_pair`。2026-05-14 测试发现：两个 58 sheet / 12万行的文件，24 个 sheet 虽然 XML bytes 不同，但 size 相同（格式/压缩差异），只有 1 个 sheet 有实质内容差异。全量解析浪费了 96% 的解析时间。

改进思路：解析前先做轻量级 ZIP 条目比对，只解析内容真的有变化的 sheet，其余 sheet 直接跳过。

## What Changes
- 新增 `_zip_get_changed_sheets(cur_bytes, prv_bytes)` 函数：ZIP 级别轻量比对，返回 size 不同的 sheet 集合
- Phase 2（`step3_download_and_compare` 中的解析+对比循环）改造：
  - 解析前先做 ZIP 预检，无实质变化的版本对直接跳过（0 diff）
  - 用 `ThreadPoolExecutor` 并行处理多个版本对
  - 保持 `_parse_excel_with_cache` 和 `_compare_pair` 的调用方式不变
- 不改输出格式，不改 `_compare_pair` / `_build_row` / `write_excel`
- 不改 `_parse_excel_lxml` 的内部逻辑

## Impact
- Affected specs: none (新增)
- Affected code: `svn_oneclick_compare.py` — `step3_download_and_compare` 函数内的 Phase 2 + 新增 `_zip_get_changed_sheets`

## ADDED Requirements

### Requirement: ZIP 预检函数
系统 SHALL 提供 `_zip_get_changed_sheets(cur_bytes, prv_bytes)` 函数，对两个 Excel 文件的 zip 条目进行轻量级比对。

#### Scenario: size 不同的 sheet 被检测
- **WHEN** cur_bytes 和 prv_bytes 中 sheet27.xml 大小分别为 2022509 和 2022376
- **THEN** 返回集合包含 `"sheet27"`

#### Scenario: size 相同但内容不同的 sheet 不被标记
- **WHEN** cur 和 prv 中 sheet28.xml 大小完全相同（如 12606 bytes），但 MD5 不同
- **THEN** 该 sheet 不被包含在返回集合中（仅格式/压缩差异，无实质内容变化）

#### Scenario: sharedStrings 变化被单独返回
- **WHEN** sharedStrings.xml 的字节长度不同
- **THEN** 返回值单独标记 `ss_changed=True`

#### Scenario: 完全无变化
- **WHEN** 所有 sheet XML 的字节长度完全相同
- **THEN** 返回空集合 + `ss_changed=False`

### Requirement: Phase 2 并行处理
Phase 2 的版本对对比 SHALL 使用 `ThreadPoolExecutor` 并行调度。

#### Scenario: 预检跳过无变化版本对
- **WHEN** 版本对 cur/prv 的 ZIP 预检发现无 sheet 有实质变化
- **THEN** 该版本对不调用 `_parse_excel_with_cache`，直接返回 0 条差异
- **AND** 不影响其他版本对的处理

#### Scenario: 有变化版本对正常对比
- **WHEN** 版本对 cur/prv 的 ZIP 预检发现有 sheet 变化
- **THEN** 正常调用 `_parse_excel_with_cache` + `_compare_pair`
- **AND** 产生与改造前完全相同的差异行列表

#### Scenario: 并行执行多个版本对
- **WHEN** 有 N 个版本对需要处理
- **THEN** 使用 `ThreadPoolExecutor(max_workers=N)` 并行提交任务
- **AND** 结果按原顺序汇总到 `all_file_results`

#### Scenario: 异常隔离
- **WHEN** 某个版本对在处理过程中抛出异常
- **THEN** 该异常被捕获记录，不影响其他版本对的处理
- **AND** 行为与改造前一致

## MODIFIED Requirements
无。

## REMOVED Requirements
无。
