# Checklist

- [x] `_regex_scan_structure` 返回的 sheet dict 含 `uses_ss` 字段
- [x] uses_ss 检测使用 bytes 搜索，不引入 XML 解析开销
- [x] Phase B ss_changed 时只标记 uses_ss=True 的 sheet
- [x] uses_ss=False 的 sheet 在 ss_changed 时回退到普通 CRC 比较
- [x] 语法验证通过（`python -m py_compile`）
- [x] graphify update 执行通过
