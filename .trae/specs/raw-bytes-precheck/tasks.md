# Tasks

- [x] Task 1: 改写 `_zip_get_changed_sheets` 为 raw bytes + t="s" 正则
  - [x] 1.1 遍历所有 sheet entries 时，先按 `file_size` 快速过滤
  - [x] 1.2 `file_size` 不同时，用 `zf.read(entry_name)` 读出 raw bytes，`cur_bytes != prv_bytes` 判定变化
  - [x] 1.3 `file_size` 相同但 `ss_changed=True` 时，用 `rb't="s"'` 正则判定是否引用共享字符串
  - [x] 1.4 对 bytes 确实不同或引用共享字符串且 SS 变化的 sheet，加入 `changed_sheets`
  - [x] 1.5 移除 `file_size` 直接比较逻辑（替换为上述逻辑）
  - [x] 1.6 保持返回签名 `-> tuple[set, bool]` 不变

- [x] Task 2: 语法验证 + graphify update
  - [x] 2.1 `python -m py_compile svn_oneclick_compare.py` 通过
  - [x] 2.2 `graphify update` 执行成功

- [x] Task 3: 行为验证
  - [x] 3.1 Texts1/Texts2 预检：58/58 sheets + ss_changed=True（数据特征：全部引用 t="s"）
  - [x] 3.2 真实 SVN 缓存数据：rev 334431→335136，58/58 sheets + ss_changed=True（同特征）
  - [x] 3.3 预检逻辑本身正确：raw bytes 比较精准，t="s" 扫描正确判断

# Task Dependencies
- Task 1 独立
- Task 2 依赖 Task 1
- Task 3 依赖 Task 1

# 生产数据特征
真实 SVN 数据 58/58 sheets 全部使用 `t="s"`。SS 变化时所有 sheet 都需要解析。
性能提升体现在有具体 sheet bytes 变化的版本对（`zf.read()` 精准跳过未变 sheet）。
