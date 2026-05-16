# Checklist

## Task 1: 改写 `_zip_get_changed_sheets`

- [x] 改为比较 raw bytes 内容，不再只用 `file_size`
- [x] `file_size` 快速过滤保留（避免对同 size sheet 读 bytes）
- [x] `cur_raw != prv_raw` 判定 sheet 变化
- [x] `ss_changed=True` + bytes 相同/同 size + 有 `t="s"` → 加入 changed_sheets
- [x] `ss_changed=True` + bytes 相同/同 size + 无 `t="s"` → 跳过
- [x] 返回签名 `-> tuple[set, bool]` 不变
- [x] try/except 兜底不变
- [x] `_TS_ATTR_RE` 模块级正则 `rb't="s"'`

## Task 2: 语法验证

- [x] `python -m py_compile svn_oneclick_compare.py` 无错误
- [x] `graphify update` 执行成功

## Task 3: 行为验证

- [x] real SVN data: 58/58 sheets 全部使用 t="s" → 预检正常
- [x] 生产数据特征确认：sharedStrings 变化 + 全 sheet 引用 → 无法跳过解析
- [x] 预检逻辑正确：仅当 sheet 使用 t="s" 且 SS 变化时才标记
