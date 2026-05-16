# 计划：ss_changed 时不标记全部 sheet 优化

## 背景

当前 sharedStrings CRC 变化时 `changed_sheets = set(all_sn)`（标记全部 58 个 sheet），导致全量解析所有 sheet×版本对，是 113 秒总耗时的 70-110 秒瓶颈。实际很多 sheet 只含数值列，不受 shared strings 变化影响。

## 实施步骤

### Step 1：Phase A 扫描时检测每个 sheet 是否引用 shared strings

`_regex_scan_structure` 中遍历 sheet XML 时检查是否有 `t="s"` 的 cell。如果没有 s-type cell，该 sheet 不受 sharedStrings 影响。

在 `_structure_cache` 的 sheet dict 中添加 `"uses_ss": bool` 字段。

### Step 2：Phase B 只对 `uses_ss=True` 的 sheet 做 ss_changed 全标记

```python
if ss_changed:
    for sn in all_sn:
        if cur_struct[sn].get("uses_ss") or prv_struct[sn].get("uses_ss"):
            if cur_struct[sn]["crc"] != prv_struct[sn]["crc"] or ss_changed:
                changed_sheets.add(sn)
else:
    # 原来的 CRC 逐个比较逻辑不变
```

实际上可以更简洁：ss_changed 时，直接比较 CRC——因为 `uses_ss` 的 sheet 即使 SS 变了，只有 CRC 也不同的 sheet 才真的需要重解析（CRC = 文件级校验，SS 变了但 sheet 的 cell ref+v 没变则 CRC 不变）。

但为了保险，ss_changed 时对使用 SS 的 sheet 不做 CRC 判断，直接标记为变化（因为 SS 引用的文本变了但 `<v>` 索引没变→CRC 相同但真实文本变了）。

### Step 3：检测方式——Phase A 快速扫描

`_regex_scan_structure` 中读取 sheet raw bytes 后，用 regex 搜索 `t="s"` 或 `t='s'`：

```python
uses_ss = b't="s"' in raw_sheet_bytes or b"t='s'" in raw_sheet_bytes
result[nm] = {"raw": raw, "crc": info.CRC, "target": target, "uses_ss": uses_ss}
```

这个检测是 O(1)——只是内存中检查 bytes 子串，不涉及 XML 解析。

### Step 4：验证语法 + graphify update

## 涉及的文件

| 文件 | 操作 |
|---|---|
| `svn_oneclick_compare.py` | `_regex_scan_structure` 增加 uses_ss 检测；Phase B 改变 ss_changed 时全标记逻辑 |
