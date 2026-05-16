# Tasks

- [x] Task 1: `_regex_scan_structure` 增加 uses_ss 字段
  - sheet raw bytes 读取后，检查 `b't="s"' in raw` 或 `b"t='s'" in raw`
  - result[nm] 增加 `"uses_ss": uses_ss`
  - 不引入 XML 解析，纯 bytes 搜索

- [x] Task 2: Phase B 修改 ss_changed 标记逻辑
  - 去掉 `changed_sheets = set(all_sn) if ss_changed else set()`
  - 改为：sharedStrings CRC 变化时，只对 uses_ss=True 的 sheet 跳过 CRC 比较直接标记
  - uses_ss=False 的 sheet 走普通 CRC 比较逻辑

- [x] Task 3: 验证语法 + graphify update

# Task Dependencies

无
