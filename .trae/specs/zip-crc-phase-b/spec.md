# ZIP CRC32 Phase B 实现精确 sheet 跳过

## Why

当前 Phase B 使用 ref:v 内容哈希需要解码 XML + regex 提取全部 cell，耗时 ~7-12s 且仍漏 shared string 纯文本变化。ZIP 元数据中每个条目已有 CRC32（对解压后完整内容计算），读取成本为零。同时比较 sharedStrings.xml 的 CRC，覆盖纯文本变化场景。

## What Changes

- `_regex_scan_structure` 恢复完整返回 `(struct_dict, ss_crc)`，将 ss_crc 缓存到 `_structure_cache` 关联的 ss_crc 缓存
- Phase B 改为 ZIP CRC32 比较：sheet 对 pair 使用 `sd["crc"]` 比较，加上 sharedStrings CRC 比较
- 删除 `_compute_sheet_content_fingerprint` 和 `_sheet_content_fp_cache`

## Impact

- Affected code: `svn_oneclick_compare.py`
- 删除 ~25 行代码，修改 ~15 行

## ADDED Requirements

### Requirement: ZIP CRC32 Sheet 跳过

系统 SHALL 使用 ZIP 条目的 CRC32 判断 sheet 是否变化。

#### Scenario: sheet CRC 不同
- **WHEN** 版本 A 和版本 B 中同一 sheet 的 ZIP CRC32 不同
- **THEN** 标记该 sheet 为变化

#### Scenario: sharedStrings CRC 不同
- **WHEN** 版本 A 和版本 B 的 sharedStrings.xml 的 ZIP CRC32 不同
- **THEN** 标记所有涉及 shared string 的 sheet 为变化

#### Scenario: 都无变化
- **WHEN** 所有 sheet CRC 和 sharedStrings CRC 都相同
- **THEN** 跳过整对版本对比

## REMOVED Requirements

### `_compute_sheet_content_fingerprint`

**Reason**: ZIP CRC32 零成本即可实现同等精确度
**Migration**: 删除函数及其调用

### `_sheet_content_fp_cache`

**Reason**: 不再需要内容指纹缓存
**Migration**: 删除全局声明和所有引用
