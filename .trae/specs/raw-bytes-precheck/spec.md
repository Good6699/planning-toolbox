# Raw Bytes 预检 Spec

## Why
当前 `_zip_get_changed_sheets` 按 ZIP entry `file_size` 比较变化。生产数据的常见场景：sharedStrings.xml 每次都变，但 sheet XML 的 `file_size` 恰好相同（`<v>123</v>` → `<v>456</v>` 同长度）→ 预检返回空集合 → 回退到全量 58 sheet 解析（14s/文件）。

改进：按 ZIP entry **raw bytes 内容**比较，`!=` 即标记变化。对 sharedStrings 变了但 sheet bytes 相同的特殊场景，用轻量正则扫描判断 sheet 是否引用共享字符串。

## What Changes
- `_zip_get_changed_sheets` 改为读出 `zf.read("xl/worksheets/sheetN.xml")` 比较 raw bytes，而非 `file_size`
- `ss_changed=True` + sheet bytes 相同时，用 `rb't="s"'` 正则搜索 raw XML 判定是否需要解析
- `_cmp_task_proc` / Phase 2 逻辑不变
- 不改其他任何代码

## Impact
- Affected specs: `ipc`（基于现状改进）`smart-sheet-parsing`（only_sheets 因此更精准）
- Affected code: `svn_oneclick_compare.py` — `_zip_get_changed_sheets` 函数体

## MODIFIED Requirements

### Requirement: 按 raw bytes 判定 sheet 变化
`_zip_get_changed_sheets` SHALL 读取 sheet XML 的原始字节内容，`cur_bytes != prv_bytes` 时标记该 sheet 为变化。

#### Scenario: cell inline value 变化被检测
- **WHEN** cur 的 sheet27.xml 中 `<v>123</v>` 变为 prv 的 `<v>456</v>`（同长度 3 字节）
- **THEN** sheet27 的 raw bytes 不同（3 字节 "123" vs "456"）
- **AND** sheet27 被加入 `changed_sheets`

#### Scenario: 纯格式/压缩差异也被标记
- **WHEN** sheet 内容完全相同但 ZIP 压缩级别不同
- **THEN** raw bytes 不同 → 被标记为变化（保守策略，不遗漏）
- **AND** 多解析几个 sheet 的代价 < 5%（通常极少发生）

#### Scenario: 字节完全相同且 ss_changed=False 则跳过
- **WHEN** cur 和 prv 的 sheet28.xml raw bytes 完全一致，且 sharedStrings 未变
- **THEN** 该 sheet 不被加入 `changed_sheets`
- **AND** 不会被 lxml 解析

### Requirement: sharedStrings 变化时只解析引用 t="s" 的 sheet
当 sheet bytes 相同但 `ss_changed=True` 时，系统 SHALL 用轻量正则扫描原始 XML bytes 判断是否包含 `t="s"` 标记。

#### Scenario: sheet 引用 sharedStrings
- **WHEN** sheet bytes 相同 + `ss_changed=True` + raw XML 包含 `t="s"`
- **THEN** 该 sheet 被加入 `changed_sheets`（保守，可能无实质差异但这极少浪费）

#### Scenario: sheet 不引用 sharedStrings
- **WHEN** sheet bytes 相同 + `ss_changed=True` + raw XML 不包含 `t="s"`
- **THEN** 该 sheet 不被加入 `changed_sheets`（sharedStrings 变化与此 sheet 无关）

#### Scenario: byte length 先快速过滤
- **WHEN** 遍历所有 sheet entries
- **THEN** 先按 `file_size` 快速比较（过滤掉 size 相同的对）
- **AND** 只对 size 不通过的 sheet 做 `zf.read() + !=` 比较（避免不必要的解压开销）

## REMOVED Requirements
无。
