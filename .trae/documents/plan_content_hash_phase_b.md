# 计划：内容哈希 Phase B 替代字节指纹实现精确 sheet 跳过

## 背景

当前 Phase B 使用 `_compute_sheet_fingerprint`（前 4KB raw XML 做 MD5）判断 sheet 是否变化，存在假阴性（漏差异）和假阳性（XML 噪音触发误判）。替换为**内容哈希**（提取 cell ref+v 值 + sharedStrings CRC 做 MD5），实现零假阴性、零假阳性的 sheet 级跳过。

## 实施步骤

### Step 1：新增 `_compute_sheet_content_fingerprint` 函数

提取 sheet XML 中所有 cell 的 ref 和 v 值，排序拼接成规范字符串，加上 SS CRC，做 MD5。

位置：紧接 `_compute_sheet_fingerprint` 之后（~L929）

### Step 2：`_regex_scan_structure` 返回 ss_crc

从 ZIP 读取 `xl/sharedStrings.xml` 的 CRC，加入返回 dict。

### Step 3：全局缓存替换

`_sheet_fp_cache` → `_sheet_content_fp_cache`，key 不变，但 value 从字节指纹改为内容指纹。

`_structure_cache` 中缓存 ss_crc。

### Step 4：修改 `_process_one_pair` 中的 Phase B

- Phase A 缓存路径写入内容指纹而非字节指纹
- Phase B 比较内容指纹判断变化 sheet
- 仍然保留 `if not changed_sheets: continue` 跳过逻辑

### Step 5：清理

`_compute_sheet_fingerprint` 保留不删（可能其他处引用），改调用方式。

### Step 6：验证语法 + graphify update

## 涉及的文件

| 文件 | 操作 | 说明 |
|---|---|---|
| `svn_oneclick_compare.py` | 修改 | 新增函数、修改 3 处逻辑 |

## 风险

- 修改了缓存架构，可能影响 `_compare_pair` 中的 `_hash` 字段——需要确认该字段是否仍在使用
