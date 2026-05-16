# SS 复用 Spec

## Why
当前每对版本对比中，sharedStrings 被解析两次：
1. `_parse_ss_values` 纯正则解析（3s）→ 指纹预检用
2. `_parse_excel_lxml` 内部 lxml fromstring（1.1s）→ 数据解析用

两个产物完全相同。指纹预检后可将 SS 值列表传入 lxml 解析阶段，跳过重复解析。

## What Changes
- `_parse_excel_lxml` 新增可选参数 `ss_values: Optional[List[str]] = None`
  - 非 None 时跳过内部 SS 解析，直接使用传入值
  - None 时保持原有 lxml 解析流程（向后兼容）
- `_cmp_task_proc` 调用 `_parse_excel_lxml` 时传入 `ss_values`（从 `_zip_get_changed_sheets` 内部获取的）
- 不改 `_parse_ss_values` 签名，不改 `_compare_pair`，不改 `_zip_get_changed_sheets`

## Impact
- Affected code: `svn_oneclick_compare.py` — `_parse_excel_lxml` 签名 + `_cmp_task_proc` 调用点
- Affected specs: `ss-fingerprint-precheck`

## MODIFIED Requirements

### Requirement: `_parse_excel_lxml` 接受可选 SS 值
函数 SHALL 接受 `ss_values` 可选参数，非 None 时跳过内部 sharedStrings.xml 解析。

#### Scenario: ss_values 传入时跳过解析
- **WHEN** `_parse_excel_lxml(raw_b, rev, ss_values=["文字1","文字2",...])` 被调用
- **THEN** 函数 SHALL 不解析 `xl/sharedStrings.xml`
- **AND** 直接使用传入的 `ss_values` 替代内部的 `shared_strings` 变量

#### Scenario: ss_values 未传时保持原行为
- **WHEN** `_parse_excel_lxml(raw_b, rev)` 被调用（无 ss_values 参数）
- **THEN** 函数 SHALL 保持原有 lxml fromstring 解析流程
- **AND** 所有现有调用点无需修改

#### Scenario: 331 条差异结果不变
- **WHEN** `_cmp_task_proc` 传入 SS 复用值
- **THEN** diff_rows 数量、内容与不改动时完全一致

#### Scenario: 性能
- **WHEN** `ss_values` 传入
- **THEN** 每对版本省 ~1.1s（lxml fromstring SS 解析）
- **AND** 32 对 / 16 子进程 净省 ~6s
