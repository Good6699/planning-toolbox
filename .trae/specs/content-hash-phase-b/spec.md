# 内容哈希 Phase B 替代字节指纹实现精确 sheet 跳过

## Why

当前 Phase B 使用 `_compute_sheet_fingerprint`（前 4KB raw XML 做 MD5）判断 sheet 是否变化，存在假阴性（前 4KB 后的差异被漏判）和假阳性（XML 属性顺序/UID 等噪音触发误判）。替换为**内容哈希**（提取 cell ref+v 值 + sharedStrings CRC 做 MD5），实现零假阴性、零假阳性的 sheet 级精确跳过。

## What Changes

- 新增 `_compute_sheet_content_fingerprint(raw_sheet_bytes, ss_crc)` 函数
- 修改 `_regex_scan_structure` 返回 sharedStrings CRC
- `_sheet_fp_cache` → `_sheet_content_fp_cache`，缓存语义从字节指纹改为内容指纹
- `_process_one_pair` 中的 Phase B 改为调用内容指纹比较
- 保留 `if not changed_sheets: continue` 跳过逻辑

## Impact

- Affected specs: 无（仅修改现有函数）
- Affected code: `svn_oneclick_compare.py`
- `_compare_pair` 中的 `_hash` 字段：确认是否仍被使用，如果已无引用则清理

## ADDED Requirements

### Requirement: 内容指纹函数

系统 SHALL 提供 `_compute_sheet_content_fingerprint` 函数。

#### Scenario: 正常调用
- **WHEN** 传入 sheet raw bytes + ss_crc
- **THEN** 提取所有 cell ref+v → 排序拼接 → MD5(数据+SS_CRC)
- **THEN** 返回 32 字符 hex 字符串

#### Scenario: 空 sheet
- **WHEN** sheet 无数据行
- **THEN** pairs 列表为空 → 返回固定的空指纹（所有空 sheet 指纹相同，正确）

## MODIFIED Requirements

### Requirement: `_regex_scan_structure` 返回 ss_crc

修改函数签名，从 `-> Optional[Dict[str, dict]]` 改为 `-> Tuple[Optional[Dict[str, dict]], int]`，第二个返回值为 sharedStrings.xml 的 CRC。

### Requirement: Phase B Sheet 跳过逻辑

`_process_one_pair` 中的 Phase B 比较使用 `_sheet_content_fp_cache` 中的内容指纹，而非 `_sheet_fp_cache` 中的字节指纹。
