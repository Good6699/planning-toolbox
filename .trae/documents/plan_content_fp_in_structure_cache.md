# 计划：_structure_cache 缓存内容指纹实现精确 sheet 跳过

## 背景

当前生产代码的演进路线：

| 阶段 | 方案 | 状态 |
|------|------|------|
| Phase A 字节指纹 | `_compute_sheet_fingerprint`：前 4KB MD5 | ❌ 已废弃（假阴性/假阳性） |
| 内容哈希 Phase B | `_compute_sheet_content_fingerprint`：ref+v 内容 MD5 | ❌ 已实施后被 ZIP CRC32 替代 |
| ZIP CRC32 Phase B | 利用 ZIP 元数据 CRC32 + uses_ss | ✅ 当前生产代码 |

### 当前生产代码架构

```
_structure_cache: Dict[str, dict]       # content_hash → {sheet_name: {raw, crc, target, uses_ss}}
_ss_crc_cache: Dict[str, int]           # content_hash → sharedStrings.xml CRC

Phase B: ZIP CRC32 + ss_crc + uses_ss → changed_sheets
```

### 当前方案的不足

ZIP CRC32 是文件级校验和，虽然读取成本为零，但有以下问题：

1. **XML 噪音触发假阳性**：ZIP CRC32 对解压后的完整 XML 内容计算。单元格顺序变化、XML 属性顺序变化、命名空间 UID 变化等非语义差异都会导致 CRC 变化，触发不必要解析。
2. **SS 文本变化全面误判**：当 `ss_changed=True` 时，所有 `uses_ss=True` 的 sheet 被标记为"需重解析"，即使这些 sheet 的 cell ref+v（即索引值）完全没有变化。实际数据没变，但因为 sharedStrings 中的文本变了，强制全量解析。
3. **无法精确跳过**：无法区分"数值变化"和"仅 SS 文本变化"，导致 Phase D 解析了大量最终无差异的行。

### 方案思路

在 `_structure_cache` 中新增 **每个 sheet 的内容指纹**（MD5 of sorted cell ref+v pairs + SS CRC），在 Phase B 中优先使用内容指纹做精确比较，ZIP CRC32 作为快速预筛。

## 设计目标

1. **零假阴性、零假阳性**的 sheet 级跳过判定
2. **不引入额外缓存**：内容指纹直接嵌入 `_structure_cache`，无需单独的 `_sheet_fp_cache` 或 `_sheet_content_fp_cache`
3. **后向兼容**：Phase A/B/C/D/E 的流水线架构不变
4. **补充而非替代**：内容指纹用于精确判定，ZIP CRC32 仍用于快速预筛

## 详细设计

### 变化 1：`_structure_cache` 值类型扩展

```python
# 当前
_structure_cache: Dict[str, dict]  # content_hash → {sheet_name: {raw: bytes, crc: int, target: str, uses_ss: bool}}

# 改为
_structure_cache: Dict[str, dict]  # content_hash → {sheet_name: {raw: bytes, crc: int, target: str, uses_ss: bool, fp: str}}
```

新增字段 `fp: str` — 32 字符 MD5 hex，计算方式：
- 提取 sheet XML 中所有 `<c r=".." ..><v>..</v></c>` 的 `(ref, v)` 对
- 按 ref（列字母+行号）排序
- 拼接为规范字符串：`ref1:v1|ref2:v2|...`
- 加上 SS CRC 后缀：`concat_str|ss:<ss_crc>`
- 取 MD5 得到 32 字符指纹

### 变化 2：Phase A 中计算并缓存 fp

`_regex_scan_structure` 的职责不变（读 raw bytes + CRC + uses_ss），新增在 `_structure_cache` 写入后立即计算 fp。

具体位置：`_process_one_pair` 中 Phase A 缓存路径（L2190-L2207），在 `_structure_cache[cur_ch] = cur_struct` 之后为每个 sheet 计算 fp。

### 变化 3：Phase B 优先使用 fp 做比较

```python
# 伪代码逻辑
for sn in all_sn:
    if sn in cur_struct and sn in prv_struct:
        if cur_struct[sn].get("fp") and prv_struct[sn].get("fp"):
            # 内容指纹精确比较
            if cur_struct[sn]["fp"] != prv_struct[sn]["fp"]:
                changed_sheets.add(sn)
        else:
            # 后备：ZIP CRC32 比较（无 fp 时的兼容路径）
            if cur_struct[sn]["crc"] != prv_struct[sn]["crc"]:
                changed_sheets.add(sn)
    else:
        changed_sheets.add(sn)  # 新增或删除的 sheet
```

**注意**：不再需要 SS 特殊处理（ss_changed 标记所有 uses_ss sheet），因为内容指纹已经编码了 SS 引用关系。SS 文本变化 → cell 的 `<v>` 索引值不变 → 但 SS CRC 变了 → 内容指纹中 `|ss:<ss_crc>` 后缀跟着变 → fp 不同 → 正确标记变化。

### 变化 4：清理

- `_ss_crc_cache` 可以移除（SS CRC 已嵌入 fp 中）
- `_compute_sheet_fingerprint`（前 4KB MD5）仍然保留给 `_compare_pair` 中空 sheet 占位用，不改动

## 性能分析

### 计算代价

每个版本每 sheet 需要一次 fp 计算：
- regex 扫描 `<c>` 标签：与 Phase D 的 regex 解析类似，但 **只提 ref 和 v**，不做 SS 替换、不做行重建
- 对于平均 2000 cell 的 sheet，预计耗时 ~2-5ms

32 版本 × 58 sheet × 2 次（cur+prv）= 3712 次 × 3ms ≈ **11 秒**

### 收益

- 消除 ZIP CRC32 的假阳性：XML 噪音不会触发误判
- 消除 SS 全标记：SS 变化时自动精确判定
- 更多 sheet 被跳过 → Phase D 解析量减少
- 当前 32 对版本总耗时 ~120s，预计节省 **15-30s**

### 是否值得

- 增加 ~11s 计算开销（Phase A 后新增）
- 节省 ~15-30s 的 Phase D 解析 + Phase E 对比
- **净收益 ~4-19s**，但精确性大幅提升（零假阳性/假阴性）

## 实施步骤

### Step 1：新增 `_compute_sheet_content_fp` 函数

- 位置：`_regex_scan_structure` 之后（~L927）
- 输入：raw_sheet_bytes, ss_crc
- 输出：32 字符 MD5 hex
- 算法：regex 提取所有 `<c r=".." ..>` 中 `<v>` 的值 → 按 ref 排序 → 拼接 → MD5(数据+"|ss:"+SS_CRC)

### Step 2：Phase A 缓存路径中计算 fp

- `_process_one_pair` 中 `_structure_cache[cur_ch] = cur_struct` 后
- 遍历 cur_struct 所有 sheet，对每个调用 `_compute_sheet_content_fp(raw, cur_ss_crc)`
- 写入 `cur_struct[sn]["fp"] = fp`
- 同理处理 prv_struct

### Step 3：Phase B 改为 fp 优先比较

- 对同时存在 cur 和 prv 的 sheet：优先比较 fp
- fp 缺失或为空时回退到 CRC 比较
- sheet 新增/删除：直接标记

### Step 4：移除 `_ss_crc_cache`

- 删除全局声明
- 删除 `_process_one_pair` 中读写 `_ss_crc_cache` 的代码
- SS CRC 仅作为 fp 计算的输入参数传入

### Step 5：验证 + graphify update

- `python -m py_compile` 验证语法
- `graphify update` 更新知识图谱

## 涉及文件

| 文件 | 操作 |
|------|------|
| `svn_oneclick_compare.py` | 新增函数 + 修改 Phase A/B + 清理 `_ss_crc_cache` |

## 风险与回退

- **风险**：fp 计算耗时超出预期 → 可降级为仅对 uses_ss 的 sheet 计算 fp，或无 SS 依赖的 sheet 仍用 CRC
- **回退**：删除 fp 字段，恢复 `_ss_crc_cache`，Phase B 恢复纯 CRC 比较
- **不影响现有功能**：`_compare_pair`、Phase D/E、日志输出完全不变
