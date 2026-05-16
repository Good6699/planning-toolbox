# ss_changed 时只标记引用 SS 的 sheet 优化

## Why

当前 sharedStrings CRC 变化时 `changed_sheets = set(all_sn)` 标记全部 58 个 sheet，导致全量解析所有 sheet×版本对，占 Phase 2 总耗时 113 秒中的 70-110 秒。实际多数 sheet 只含数值列，不受 shared strings 变化影响。

## What Changes

- `_regex_scan_structure` 中 sheet dict 增加 `uses_ss: bool` 字段，用 bytes 子串搜索检测
- Phase B 中 ss_changed 时不再标记全部 sheet，只标记 `uses_ss=True` 的 sheet；uses_ss=False 的 sheet 回退到普通 CRC 对比逻辑

## Impact

- Affected code: `svn_oneclick_compare.py`
- 改动量：+3 行 uses_ss 检测，+6 行 Phase B 标记逻辑

## ADDED Requirements

### Requirement: uses_ss 检测

系统 SHALL 在 Phase A 扫描 sheet 结构时检测该 sheet 是否引用 shared strings。

#### Scenario: sheet 含 t="s" 的 cell
- **WHEN** sheet raw bytes 包含 `t="s"` 或 `t='s'`
- **THEN** `uses_ss = True`

#### Scenario: sheet 无 s-type cell
- **WHEN** sheet raw bytes 不包含 `t="s"` 或 `t='s'`
- **THEN** `uses_ss = False`

### Requirement: ss_changed 时精准标记

系统 SHALL 在 sharedStrings CRC 变化时只标记 uses_ss=True 的 sheet。

#### Scenario: ss_changed + sheet uses_ss
- **WHEN** sharedStrings CRC 不同，且 sheet 的 uses_ss=True
- **THEN** 标记该 sheet 为变化

#### Scenario: ss_changed + sheet not uses_ss
- **WHEN** sharedStrings CRC 不同，但 sheet 的 uses_ss=False
- **THEN** 不自动标记，回退到普通 CRC 比较

## MODIFIED Requirements

### Requirement: Phase B 标记逻辑

原来 `changed_sheets = set(all_sn) if ss_changed else set()` 改为区分 uses_ss 的逐 sheet 判断。
