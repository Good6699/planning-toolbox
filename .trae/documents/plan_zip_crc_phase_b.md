# 计划：ZIP CRC32 替代内容哈希实现 sheet 跳过

## 背景

当前 Phase B 使用 ref:v 内容哈希（解码 XML + regex 提取全部 cell ref+v）判断 sheet 是否变化，开销 ~7-12s 且仍漏 shared string 文本变化。ZIP 元数据中每个条目已有 CRC32 校验和（对**解压后完整内容**计算），读取成本为零。同时比较 sharedStrings.xml 的 CRC 变化，覆盖纯文本变化场景。

## 实施步骤

### Step 1：`_regex_scan_structure` 同时读取 sharedStrings CRC

返回值已返回 `(struct_dict, ss_crc)`，但当前代码已改为只取 `struct_dict`。恢复接收第二个返回值并传递给 Phase B。

### Step 2：Phase B 改为 ZIP CRC32 比较

- sheet 变化判定：`sd["crc"]`（ZIP 条目 CRC）是否相同
- 额外判定：sharedStrings.xml 的 CRC 是否变化 → 如有变化，所有涉及 shared string 的 sheet 标记为"需重新解析"
- 删掉 `_compute_sheet_content_fingerprint` 及相关调用

### Step 3：清理

去掉 `_compute_sheet_content_fingerprint` 函数，去掉 `_sheet_content_fp_cache` 缓存（不再需要）。

### Step 4：验证语法 + graphify update

## 涉及的文件

| 文件 | 操作 |
|---|---|
| `svn_oneclick_compare.py` | 修改 Phase A+B 逻辑，清理无用代码 |
