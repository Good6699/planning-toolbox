# Checklist

## Task 1: 改写 `_zip_get_changed_sheets`

- [x] sharedStrings 值列表正确解析（纯正则 `_SS_TEXT_RE`，不用 lxml）
- [x] 正则 `_SS_V_RE` 正确提取 t="s" 引用索引
- [x] 索引解析为实际文字 `ss_values[idx]`
- [x] MD5 指纹正确比较
- [x] `ss_changed=False` 时不解析 SS（节省开销）
- [x] raw bytes 不同时直接标记变化（不经过 SS 指纹，省性能）
- [x] SS 懒加载：首次遇到 t="s" sheet 时才解析
- [x] try/except 兜底

## Task 2: 语法验证

- [x] `python -m py_compile svn_oneclick_compare.py` 无错误
- [x] `graphify update` 执行成功

## Task 3: 行为验证

- [x] Texts1/Texts2: 1 sheet detected, 57 skipped, 6.0s
- [x] 4/8 diffs correct
- [x] 真实 SVN rev334431→335136: 2 sheets detected, 56 skipped, 5.9s
- [x] 8 diffs via _cmp_task_proc
