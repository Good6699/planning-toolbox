# Tasks

## Task 1: 新增 `_compute_sheet_content_fp` 函数

- [ ] 位置：`_regex_scan_structure` 之后（L927~L928），`_compute_sheet_fingerprint` 之前
- [ ] 签名：`def _compute_sheet_content_fp(raw_sheet_bytes: bytes, ss_crc: int) -> str`
- [ ] 算法实现：
  - text = raw_sheet_bytes.decode("utf-8", errors="replace")
  - regex 匹配全部 `<c r="([A-Z]+)(\d+)"[^>]*>.*?</c>` 片段
  - 从每个片段提取 ref 和 `<v>` 值
  - 按 ref 字符串排序
  - 拼接：`ref1:v1|ref2:v2|...|ss:<ss_crc>`
  - 返回 hashlib.md5(concat.encode()).hexdigest()
- [ ] 异常保护：任何异常 return `""`
- [ ] 空 sheet（无 cell）：返回 `hashlib.md5(f"|ss:{ss_crc}".encode()).hexdigest()`

### 涉及代码行
- 新增 ~L928（在 `_regex_scan_structure` 和 `_compute_sheet_fingerprint` 之间）

---

## Task 2: Phase A 缓存路径中计算 fp

- [ ] cur_struct 路径：`_structure_cache[cur_ch] = cur_struct`（L2194）之后，立即遍历 `cur_struct.items()`，调用 `_compute_sheet_content_fp(sd["raw"], cur_ss_crc)`，结果写入 `sd["fp"]`
- [ ] prv_struct 路径：`_structure_cache[prv_ch] = prv_struct`（L2205）之后，同理遍历计算 fp
- [ ] fp 写入发生在缓存写入之后，确保缓存命中时跳过 fp 计算

### 涉及代码行
- L2194 之后新增 ~7 行
- L2205 之后新增 ~7 行

---

## Task 3: Phase B 改为 fp 优先比较

- [ ] 删除 L2211：`ss_changed = _ss_crc_cache.get(cur_ch, 0) != _ss_crc_cache.get(prv_ch, 0)`
- [ ] 重写 L2212-L2220 的循环体为 fp 优先比较逻辑
- [ ] fp 存在时比较 fp，fp 缺失/为空时回退到 CRC 比较
- [ ] sheet 新增/删除逻辑不变

### 涉及代码行
- L2209-L2220

---

## Task 4: 移除 `_ss_crc_cache`

- [ ] 删除 L145：`_ss_crc_cache: Dict[str, int] = {}`
- [ ] 删除 L2195：`_ss_crc_cache[cur_ch] = cur_ss_crc`
- [ ] 删除 L2206：`_ss_crc_cache[prv_ch] = prv_ss_crc`

### 涉及代码行
- L145, L2195, L2206

---

## Task 5: 验证语法 + graphify update

- [ ] `python -m py_compile svn_oneclick_compare.py` 验证语法
- [ ] `$env:PYTHONPATH="py_modules"; python -m graphify update .`
- [ ] 检查 Phase B comment（L2209）是否需更新（改为描述 fp 比较逻辑）

### 涉及
- 终端命令执行

---

# Task Dependencies

无依赖关系，可按 1→2→3→4→5 串行执行。
