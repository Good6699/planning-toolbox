# Checklist

## Task 1: 新增 `_compute_sheet_content_fp` 函数

- [x] 函数定义在正确位置（`_regex_scan_structure` 之后，`_compute_sheet_fingerprint` 之前）
- [x] 签名包含 `raw_sheet_bytes: bytes` 和 `ss_crc: int`，返回 `str`
- [x] regex 正确匹配所有 `<c r="..">..</c>` 片段（使用已有的 `_re_scan_cell` 或等价模式）
- [x] 从每个匹配中正确提取 ref 和 v 值
- [x] 按 ref 字符串排序
- [x] 拼接格式正确：`ref1:v1|ref2:v2|...|ss:<ss_crc>`
- [x] 空 sheet 正确处理（无 cell 时直接返回 MD5 of `|ss:<ss_crc>`）
- [x] 异常保护：任何 Exception 返回 `""`
- [x] 使用 `hashlib.md5`，返回 32 字符 hex

## Task 2: Phase A 缓存路径中计算 fp

- [x] cur_struct 缓存后立即遍历计算 fp：`for sn, sd in cur_struct.items(): sd["fp"] = ...`
- [x] prv_struct 缓存后同理遍历计算 fp
- [x] `_compute_sheet_content_fp` 传入正确的 `sd["raw"]` 和 `cur_ss_crc` / `prv_ss_crc`
- [x] 缓存命中时跳过 fp 计算（因为 `_structure_cache` 中已有 fp）
- [x] `_MAX_STRUCTURE_CACHE` 清理逻辑不影响 fp 字段（dict 整体删除）

## Task 3: Phase B 改为 fp 优先比较

- [x] 删除 `ss_changed = _ss_crc_cache.get(cur_ch, 0) != _ss_crc_cache.get(prv_ch, 0)`
- [x] 循环体：两个 sheet 都存在时优先比较 fp
- [x] fp 缺失/为空时回退到 CRC 比较
- [x] 仅一个 sheet 存在时直接标记变化
- [x] changed_sheets 为空时跳过逻辑不受影响
- [x] Phase B 注释行更新为描述 fp 比较逻辑

## Task 4: 移除 `_ss_crc_cache`

- [x] 全局声明 `_ss_crc_cache: Dict[str, int] = {}` 已删除
- [x] `_process_one_pair` 中两个 `_ss_crc_cache[...] = ...` 写入已删除
- [x] 代码中无残留的 `_ss_crc_cache` 引用
- [x] `_regex_scan_structure` 的 ss_crc 返回值仍被正确使用（作为 fp 计算输入）

## Task 5: 验证语法 + graphify update

- [x] `python -m py_compile svn_oneclick_compare.py` 通过无错误
- [x] `graphify update` 执行成功
- [x] 最终代码无 `_ss_crc_cache` 残留引用
- [x] 最终代码中 `_compute_sheet_fingerprint` 仍然存在且被使用
