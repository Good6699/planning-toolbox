# 计划：Phase C 行级跳过 + 性能优化

## 问题清单

根据日志 [分析1.txt](file:///c:/Users/admin/.qclaw/workspace/临时辅助文件/分析1.txt) 识别出 5 个问题：

| # | 问题 | 症状 | 根因 |
|---|------|------|------|
| P1 | **Phase D 全量解析** | SS 解析从 30s 降到 3s 后瓶颈仍在 Phase D+E（每对 20-50s） | `changed_rows=None`，Phase C 行级跳过未实现 |
| P2 | **越解析越慢** | 第 1 对 33s → 第 24 对 106s | 内存积累 → GC 压力增加 |
| P3 | **差异量两极分化** | 14 对 ~12k 条，18 对 1-10 条 | 可能是数据特征（间隔版本大量修改），但也可能是内容指纹误判 |
| P4 | **汇总 12372 << 16.6w** | 各对差异之和 ~16.6w，去重后仅 1.2w | dedupe 逻辑合理（相同 ID 多版本操作合并），但需验证 |
| P5 | **缓存命中 0/0** | 缓存统计无效 | `_parsed_cache` 不被 Phase A→E 路径使用，正常 |

## 方案

### 核心优化 — 实现 Phase C 行级指纹

**目标**：仅解析变化行，跳过未变化行，使 Phase D 耗时与变化行数成正比而非与 sheet 总行数成正比。

#### 设计与变更

##### Step 1：新增 `_compute_row_fingerprint` 函数

```python
def _compute_row_fingerprint(row_xml: str) -> str:
    """行级指纹：提取该行所有 cell 的 ref+v → MD5"""
    pairs = []
    for cm in _re_scan_cell.finditer(row_xml):
        ref = cm.group(1) + cm.group(2)
        vm = _re_scan_v.search(cm.group(3))
        v = vm.group(1) if vm else ""
        pairs.append(f"{ref}:{v}")
    pairs.sort()
    concat = "|".join(pairs)
    return hashlib.md5(concat.encode()).hexdigest()
```

- 位置：`_compute_sheet_content_fp` 之后（~L950）
- 输入：单行 XML（`<row r="N">...` 内部的 cell 部分）
- 输出：32 字符 MD5
- 异常保护：任何异常返回 `""`

##### Step 2：新增 `_row_fp_cache` 全局缓存

```python
_row_fp_cache: Dict[str, Dict[int, str]] = {}  # content_hash → {row_num: fp}
_MAX_ROW_FP_CACHE = 30
```

- 位置：`_structure_cache` 声明之后（~L145）
- key：版本的 content_hash
- value：`{row_num: row_fingerprint}` 字典

##### Step 3：Phase A 扩展 — 缓存行指纹

在 `_process_one_pair` 中，Phase A 写入 `_structure_cache` 后，同时计算每行的指纹并写入 `_row_fp_cache`。

```python
# 在 cur_struct 缓存后
row_fp_map = {}
for sn, sd in cur_struct.items():
    text = sd["raw"].decode("utf-8", errors="replace")
    row_fp_map[sn] = {}
    for row_m in _re_scan_row.finditer(text):
        rn = int(row_m.group(1))
        row_fp_map[sn][rn] = _compute_row_fingerprint(row_m.group(2))
_row_fp_cache[cur_ch] = row_fp_map
```

##### Step 4：Phase B 扩展 — 输出变化行集合

Phase B 的 `changed_sheets` 保持不变，新增对每个变化 sheet 的**变化行集合**计算：

```python
changed_rows_map = {}  # sn → set of changed row numbers
for sn in all_sn:
    if sn in cur_struct and sn in prv_struct:
        # ... 现有 fp/crc 比较逻辑 ...
        if should_process:  # sheet 变化
            changed_sheets.add(sn)
            # 比较行指纹
            cur_rows = _row_fp_cache.get(cur_ch, {}).get(sn, {})
            prv_rows = _row_fp_cache.get(prv_ch, {}).get(sn, {})
            all_rows = set(cur_rows) | set(prv_rows)
            changed_rows_set = set()
            for rn in all_rows:
                if cur_rows.get(rn) != prv_rows.get(rn):
                    changed_rows_set.add(rn)
            changed_rows_map[sn] = changed_rows_set
    # ... 新增/删除 sheet 的处理 ...
```

##### Step 5：Phase D 传 changed_rows

```python
for sn in changed_sheets:
    cur_raw = cur_struct[sn]["raw"]
    prv_raw = prv_struct[sn]["raw"]
    cr = changed_rows_map.get(sn)  # may be None = 全量
    cur_sd = _regex_parse_sheet_rows(cur_raw, cur_ss, cr, ic, tr)
    prv_sd = _regex_parse_sheet_rows(prv_raw, prv_ss, cr, ic, tr)
```

`_regex_parse_sheet_rows` 的 `changed_rows is None` 时仍然全量解析（兼容），有值时跳过未变化行。

#### 性能预估

| 情况 | 变化行数 | Phase D 耗时 |
|------|---------|:-----------:|
| 当前（全量） | ~4000/行 × 58 sheet | ~40s |
| 优化后（行跳过） | ~100/行 × 10 sheet | **~1s** |

如果 `changed_sheets` 中有 10 个 sheet 各变化 100 行，Phase D 从 40s 降到 ~1s。

---

### P2 修复 — 减少内存压力和 GC

##### Step 6：`_process_one_pair` 中及时释放大对象

```python
# Phase E 后，在 return 前
cur_struct.clear()
prv_struct.clear()  
# 或 del cur_struct, del prv_struct
```

实际上 `cur_struct` / `prv_struct` 是 `_structure_cache` 的引用，不能 clear。但 `cur_parsed` / `prv_parsed` 是临时构造的大对象，return 后应尽快释放。

**更有效的方式**：在 `_process_one_pair` 末尾显式 `del` 大局部变量：

```python
del cur_parsed, prv_parsed, cur_sheets, prv_sheets, cur_map, prv_map
del cur_ss, prv_ss
```

##### Step 7：对比循环中调用 gc.collect

在每处理完一批版本对（如每 8 个）后显式调用 gc.collect。

实际上 8 线程同时运行时，主线程的 `as_completed` 循环每完成一个结果就处理一个。可以在主线程的循环中添加定期 gc：

```python
gc_count = 0
for f in as_completed(futures):
    ...处理结果...
    gc_count += 1
    if gc_count % 8 == 0:
        gc.collect()
```

---

### P3 验证 — 添加日志确认行级跳过效果

##### Step 8：Phase B 输出变化信息

```python
_log(f"    {fname} r{cur} vs r{prv}: {len(changed_sheets)} sheet 变化，{sum(len(r) for r in changed_rows_map.values())} 行变化")
```

如果大部分行都被标记为"变化"（接近全量），则说明内容指纹仍有问题；如果只有少量行变化，则验证优化效果。

---

### P4 验证 — 添加差异量汇总日志

##### Step 9：去重前后分别统计

```python
for fn, file_results in all_file_results.items():
    raw_count = len(file_results)
    deduped = _dedupe_by_id(file_results)
    _log(f"  {fn}: {len(deduped)} 条差异（去重前 {raw_count} 条）")
```

---

### P5 修复 — 缓存统计兼容新架构

##### Step 10：修改缓存日志

当前 `_parsed_cache` 不被新架构使用，0/0 是正常值，但易引起困惑。改为只在 `_byte_cache_hits + _byte_cache_misses > 0` 时输出字节缓存，解析缓存统计改为报告 `_ss_crc_cache` + `_structure_cache` + 行指纹缓存的命中情况。

或在日志中省略 `0/0` 的行，避免信息噪音。

---

## 涉及文件

| 文件 | 操作 |
|------|------|
| `svn_oneclick_compare.py` | 新增 `_compute_row_fingerprint`、`_row_fp_cache`、修改 Phase A/B/D、添加日志、修改缓存统计 |

## 风险

- **行指纹计算开销**：每行做一次 MD5 可能增加 Phase A 耗时
  - 缓解：行指纹只在首次缓存时计算一次
  - 缓解：行指纹是纯字符串操作 + MD5（较 cell 解析+SS 替换轻量得多）
- **行指纹误判**：行内 XML 属性变化但值不变 → 假阳性
  - 缓解：`_compute_row_fingerprint` 只提取 `ref:v`，忽略属性顺序，与内容指纹一致
- **实施复杂度**：本次修改涉及 Phase A/B/D 三个阶段
  - 分 Step 逐一实施验证
