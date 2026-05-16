# Tasks

- [x] Task 1: 改写 `_zip_get_changed_sheets` 新增 SS 解析指纹
  - [x] 1.1 `ss_changed=True` + 首次遇到 `t="s"` sheet 时懒加载解析 sharedStrings（纯正则，不用 lxml）
  - [x] 1.2 用 `_SS_TEXT_RE` 正则提取 sharedStrings 文本值
  - [x] 1.3 用 `_SS_V_RE` 正则从 sheet raw XML 提取所有 t="s" 引用索引
  - [x] 1.4 `ss_values[idx]` 解析为实际文字，MD5 指纹比较
  - [x] 1.5 `ss_changed=False` 时不解析 SS（节省开销）
  - [x] 1.6 保持返回签名不变

- [x] Task 2: 语法验证 + graphify update
  - [x] 2.1 `python -m py_compile svn_oneclick_compare.py` 通过
  - [x] 2.2 `graphify update` 执行成功

- [x] Task 3: 行为验证
  - [x] 3.1 Texts1/Texts2: 1/58 sheets detected, 57 skipped, 6.0s ✓
  - [x] 3.2 `_cmp_task_proc`: 4/8 diffs correct ✓
  - [x] 3.3 真实 SVN 数据: 2/58 sheets detected, 56 skipped, 5.9s ✓
  - [x] 3.4 完整对比: 8 diffs, 9.2s (only parsed 2 sheets vs 58)

# Task Dependencies
- Task 1 独立
- Task 2 依赖 Task 1
- Task 3 依赖 Task 1
