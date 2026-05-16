# SharedStrings 解析指纹 Spec

## Why
当前 `raw-bytes-precheck` 能精准检测 sheet raw bytes 不同的情况。但生产数据中 sharedStrings.xml 每次 SVN 提交都变，且 58/58 sheets 都使用 `t="s"` → 全量解析无法跳过。

改进：预检时解析 sharedStrings 实际文字值 + 轻量正则扫描 sheet raw XML 提取引用索引 → 解析成真实文字 → 计算 hash。hash 相同即内容未变，即使 sharedStrings 表本身变了。

## What Changes
- `_zip_get_changed_sheets` 新增 sharedStrings 值解析
- 对 sheet raw bytes 相同但 `ss_changed=True` 的 sheet，用正则提取 `t="s"` 引用的索引值，解析为实际文字后计算 MD5 hash
- hash 不同 → 加入 `changed_sheets`；hash 相同 → 跳过（内容未变）
- `_cmp_task_proc` / Phase 2 逻辑不变
- 不改其他任何代码

## Impact
- Affected specs: `raw-bytes-precheck`（在其基础上进一步优化）
- Affected code: `svn_oneclick_compare.py` — `_zip_get_changed_sheets` 函数体

## ADDED Requirements

### Requirement: sharedStrings 值解析 + sheet 指纹
`_zip_get_changed_sheets` SHALL 解析 `xl/sharedStrings.xml` 的文本值列表，对 sheet raw bytes 相同但 `ss_changed=True` 的 sheet，用正则 `rb't="s"[^>]*><v>(\d+)</v>'` 提取索引，解析为实际文字，计算 MD5 指纹。

#### Scenario: sharedStrings 变了但 sheet 解析值未变则跳过
- **WHEN** cur sharedStrings[5827] = "裂隙秘境" → prv sharedStrings[5827] = "裂隙秘境（已开启）"
- **AND** sheet27.xml 引用索引 `[1, 2, 3]`（不包含 5827）
- **THEN** sheet27 的解析后 hash 相同
- **AND** sheet27 不加入 `changed_sheets`

#### Scenario: sharedStrings 变了且 sheet 解析值也变了则标记
- **WHEN** sharedStrings[0] 从 "旧文字1" 变为 "新文字1"
- **AND** sheet28.xml 引用索引包含 `[0, 5, 12]`
- **THEN** sheet28 的解析后 hash 不同
- **AND** sheet28 加入 `changed_sheets`

#### Scenario: raw bytes 不同直接标记
- **WHEN** sheet XML raw bytes `cur != prv`
- **THEN** 直接加入 `changed_sheets`（不经过 SS 解析指纹）

#### Scenario: sharedStrings 未变则跳过 SS 解析
- **WHEN** `ss_changed=False`
- **THEN** 不解析 sharedStrings 值列表
- **AND** 逻辑与当前版本完全一致

#### Scenario: 性能
- **WHEN** 预检 1 对版本（58 sheets）
- **THEN** sharedStrings 解析 0.1s + regex 扫描 0.3s = 0.4s 预检
- **AND** 对比 lxml 全量解析 14s 快了 35 倍
