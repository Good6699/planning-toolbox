# 规范：_structure_cache 缓存内容指纹实现精确 sheet 跳过

## 概述

当前 Phase B 使用 ZIP CRC32 + ss_changed + uses_ss 的组合判断 sheet 是否变化，存在 XML 噪音假阳性和 SS 文本变化全面误判问题。本规范将内容指纹（MD5 of sorted cell ref+v pairs + SS CRC）嵌入 `_structure_cache`，替代独立的 `_ss_crc_cache` 和 ZIP CRC32 比较逻辑，实现零假阳性/假阴性的 sheet 级精确跳过。

## 架构变化

### 缓存结构变化

```
[当前]
_structure_cache: Dict[str, dict]       # content_hash → {sheet_name: {raw, crc, target, uses_ss}}
_ss_crc_cache: Dict[str, int]           # content_hash → sharedStrings.xml CRC  ← 独立缓存

[变更后]
_structure_cache: Dict[str, dict]       # content_hash → {sheet_name: {raw, crc, target, uses_ss, fp}}
                                        #                                                            ↑ 新增 fp 字段
# _ss_crc_cache 移除
```

### 流水线变化

- **Phase A**：新增 fp 计算步骤（结构扫描后立即计算）
- **Phase B**：比较逻辑从 CRC + ss_changed + uses_ss 改为 fp 优先比较，CRC 作为后备
- **Phase C/D/E**：完全不变

## 详细需求

### REQ-1：`_compute_sheet_content_fp` 函数

**签名**：`def _compute_sheet_content_fp(raw_sheet_bytes: bytes, ss_crc: int) -> str`

**位置**：`_regex_scan_structure` 之后，`_compute_sheet_fingerprint` 之前（~L928）

**算法**：
1. XML 解码为 utf-8
2. regex 匹配所有 `<c r="COL_ROW"...>...</c>` 片段
3. 从每个片段中提取 ref（`r="..."`）和 v 值（`<v>...</v>`）
4. 按 ref 字符串排序
5. 拼接为规范字符串：`ref1:v1|ref2:v2|...`
6. 当无 cell 时（空 sheet），拼接字符串为空
7. 追加 SS CRC：`concat_str|ss:<ss_crc>`
8. 计算 MD5，返回 32 字符 hex

**错误处理**：任何异常返回空字符串 `""`（触发 Phase B 回退到 CRC 比较）

### REQ-2：Phase A 扩展 — 缓存 fp

**位置**：`_process_one_pair` 中 L2194（`_structure_cache[cur_ch] = cur_struct`）之后

**逻辑**：
```python
# Phase A 写入缓存后立即计算 fp
for sn, sd in cur_struct.items():
    sd["fp"] = _compute_sheet_content_fp(sd["raw"], cur_ss_crc)
# 同理在 prv_struct 写入后
for sn, sd in prv_struct.items():
    sd["fp"] = _compute_sheet_content_fp(sd["raw"], prv_ss_crc)
```

**注意**：fp 只在首次缓存时计算一次，后续命中 cache 直接复用。

### REQ-3：Phase B 改为 fp 优先比较

**位置**：`_process_one_pair` 中 L2209-L2220

**逻辑**：
```python
all_sn = set(cur_struct) | set(prv_struct)
changed_sheets = set()
for sn in all_sn:
    if sn in cur_struct and sn in prv_struct:
        cur_fp = cur_struct[sn].get("fp")
        prv_fp = prv_struct[sn].get("fp")
        if cur_fp and prv_fp:
            # 内容指纹精确比较（零假阴性/假阳性）
            if cur_fp != prv_fp:
                changed_sheets.add(sn)
        else:
            # 后备：ZIP CRC32 比较（fp 缺失时的兼容路径）
            if cur_struct[sn]["crc"] != prv_struct[sn]["crc"]:
                changed_sheets.add(sn)
    else:
        # sheet 新增或删除 → 必定变化
        changed_sheets.add(sn)
```

**注意**：
- 不再需要 `ss_changed` 变量
- 不再需要 `uses_ss` 检查
- 不再需要 `_ss_crc_cache` 查询
- fp 缺失回退到 CRC 比较

### REQ-4：移除 `_ss_crc_cache`

**删除内容**：
1. 全局声明 L145：`_ss_crc_cache: Dict[str, int] = {}`
2. L2195：`_ss_crc_cache[cur_ch] = cur_ss_crc`
3. L2206：`_ss_crc_cache[prv_ch] = prv_ss_crc`
4. L2211：`ss_changed = _ss_crc_cache.get(cur_ch, 0) != _ss_crc_cache.get(prv_ch, 0)`

**保留**：`_regex_scan_structure` 仍然返回 `ss_crc`（作为 fp 计算的输入），但不再存入独立缓存。

### REQ-5：保留 `_compute_sheet_fingerprint`

`_compute_sheet_fingerprint`（前 4KB MD5）在 L2283 被用于 `_compare_pair` 中空 sheet 占位。保持不变。

## 性能要求

- 单 sheet fp 计算 ≤ 5ms（2000 cell 规模）
- 总 fp 计算开销 ≤ 15s（32 版本 × 58 sheet × 2）
- Phase B fp 比较本身耗时 ≤ 1ms（纯内存字符串比较）
- 不增加 `_structure_cache` 内存占用 > 10%（每个 sheet 多一个 32 字符字符串）

## 兼容性

- 所有 `_regex_scan_structure` 调用方无需修改（返回类型不变）
- `_compare_pair` 完全不变
- Phase D/E 完全不变
- 日志输出完全不变
- fp 缺失 → 自动降级到 CRC 比较（零破坏性）

## 涉及文件

| 文件 | 操作 |
|------|------|
| `svn_oneclick_compare.py` | 新增函数 + 修改 Phase A + 重写 Phase B + 清理 `_ss_crc_cache` |

## 测试策略

- `python -m py_compile` 验证语法
- 对比 32 版本对的输出与当前生产代码的一致性
- 检查 `changed_sheets` 数量是否与预期一致（无遗漏、无多余）
