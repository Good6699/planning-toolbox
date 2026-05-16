# 计划：消除 SS 文本变化导致的假阳性差异

## 问题根因

SS 文本变化 → 所有引用该索引的单元格被标记为"修改"

```
SS 索引 100: "foo" → "bar"
        ↓
单元格 A1  <v>100</v>  → SS 替换为 "foo" → Phase E 对比 → != "bar" → 标记修改
单元格 B7  <v>100</v>  → SS 替换为 "foo" → Phase E 对比 → != "bar" → 标记修改
...
10 个 sheet × 500 个引用 = 5000 条假差异
```

一个 SS 文本变化可以产生数千条假阳性差异。12360 条差异中大部分是这样来的。

## 核心方案

### 原则

- **SS 文本变化单独检测、单独报告**，而不是混在单元格差异里
- **单元格差异只对比 `<v>` 索引值**（SS 索引或数值本身），不对比 SS 替换后的文本
- fp / 行级指纹 **不含 SS CRC**（SS 变化不触发重解析）

### 变更列表

#### 改动 1：fp 去掉 SS CRC

```python
# 当前
fp = MD5(ref1:v1|ref2:v2|...|ss:CRC)
# 改为
fp = MD5(ref1:v1|ref2:v2|...)
```

这样 SS 纯文本变化不会触发 Phase B → 不会标记 sheet 变化 → 不会进 Phase D 空转。

**注意**：`_compute_sheet_content_fp` 的 `ss_crc` 参数保留，只是不计入指纹。函数签名不变，不影响调用方。

---

#### 改动 2：`_regex_parse_sheet_rows` 存储原始 `<v>` 值

当前 SS 单元格直接替换为文本：

```python
# 当前
if ct == "s" and v.strip().isdigit():
    v = shared_strings[idx]  # 替换为文本
# cells[cl] = v
```

改为同时存储原始值和解析值：

```python
# 改为
cell_info = {"raw": v, "text": ""}
if ct == "s" and v.strip().isdigit():
    idx = int(v)
    cell_info["raw"] = v
    cell_info["text"] = shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
else:
    cell_info["raw"] = v
    cell_info["text"] = v
# cells[cl] = cell_info  → {"raw": "100", "text": "实际文本"}
```

变更范围：`_regex_parse_sheet_rows` 中约 5 行。

---

#### 改动 3：`_compare_pair_merge` 按 `raw` 值对比

```python
# 当前
if cur_cells.get(col) != prv_cells.get(col):
    modified_cols.append(...)

# 改为
if cur_cells.get(col, {}).get("raw") != prv_cells.get(col, {}).get("raw"):
    modified_cols.append(...)
```

只对比 `raw` 值（SS 索引或数值本身），SS 文本变化不触发单元格差异。

---

#### 改动 4：`_build_row` 输出 `text` 值

当前直接取单元格值赋值。改为取 `text` 字段：

```python
# 当前
row["col_name"] = cells.get(col, "")
# 改为
cinfo = cells.get(col, {})
row["col_name"] = cinfo.get("text", "") if isinstance(cinfo, dict) else str(cinfo)
```

**兼容注意**：未变化 sheet 的空占位 `{"map": {}, "_hash": same_hash}` 中 `_hash` 和原有的 `_regex_parse_sheet_rows` 返回格式需要兼容处理。

---

#### 改动 5：SS 变化单独检测并输出

Phase E 后，新增独立检测：

```python
ss_diffs = []
if cur_ss_crc != prv_ss_crc and cur_ss and prv_ss:
    for i, (cur_t, prv_t) in enumerate(zip(cur_ss, prv_ss)):
        if cur_t != prv_t:
            ss_diffs.append({
                "操作": "修改",
                "ID": f"_SS_{i}",
                "当前版本": cur,
                "前一版本": prv,
                "sheet": "_sharedStrings",
                "SS索引": i,
                "旧文本": cur_t,
                "新文本": prv_t,
            })
```

这些 SS diff 随普通 diff 一起返回。

**注意**：需要 `cur_ss_crc` / `prv_ss_crc` 能在缓存命中时获取到 → 已通过 `_ss_crc_cache` 保证。

---

### 与当前架构的关系

| 阶段 | 当前行为 | 变更后 |
|------|---------|--------|
| Phase A | fp 含 SS CRC | fp 不含 SS CRC |
| Phase B | SS 变化触发 fp 不同 → 标记 sheet | SS 变化不触发 |
| Phase C | 行指纹 = `ref:v` → 不受 SS 影响 | 不变 |
| Phase D | SS 变化时 cr=None → 全量解析 | 不再因 SS 变化触发全量解析 |
| Phase E | 对比 SS 替换后的文本 → 假阳性 | 对比 raw `<v>` 值 → 零假阳性 |
| 新增 | — | SS diff 独立检测 |

### 性能影响

| 场景 | 当前耗时 | 变更后 | 原因 |
|------|:-------:|:------:|------|
| SS 变化 + 0 行变化 | 30-60s | **~1s** | 不再全量解析 58 sheet |
| 正常行变化 | ~5-15s | ~5-15s | 不变 |
| SS 变化 + 也有行变化 | ~20-40s | ~5-15s | 只解析有行变化的 sheet |
| SS diff 计算 | 无 | <1s | 纯字符串比较 |

**预估 Phase 2 总耗时：343s → ~80-120s**

### 正确性变化

| 场景 | 当前结果 | 变更后结果 |
|------|---------|-----------|
| 数值变化 | ✅ 正确 | ✅ 正确 |
| 删/增行 | ✅ 正确 | ✅ 正确 |
| SS 文本变 + v 索引不变 | ❌ 12000 条假阳性 | ✅ 报告为独立 SS diff |
| SS 文本变 + v 索引变 | ✅ 正确 | ✅ 正确（raw 不同）+ SS diff |

### 涉及文件

| 文件 | 操作 |
|------|------|
| `svn_oneclick_compare.py` | 改 `_compute_sheet_content_fp`、`_regex_parse_sheet_rows`、`_compare_pair_merge`、`_build_row`；新增 SS diff 检测 |

### 实施步骤

| Step | 改动 |
|------|------|
| 1 | fp 去掉 SS CRC |
| 2 | `_regex_parse_sheet_rows` 存储 `{"raw", "text"}` |
| 3 | `_compare_pair_merge` 按 `raw` 对比 |
| 4 | `_build_row` 输出 `text` |
| 5 | Phase E 后新增 SS diff 检测 |
| 6 | 验证语法 + graphify update |
