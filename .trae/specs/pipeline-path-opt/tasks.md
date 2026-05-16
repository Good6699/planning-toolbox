# Tasks

- [x] Task 1: 改 `_cmp_worker.py` 接收路径代替 bytes
  - [x] 1.1 参数元组改为 `(cur_path, prv_path, cur, prv, fname, tr, id_col, output_cols)`
  - [x] 1.2 从路径读取 bytes → 组装 `_cmp_task_proc` 参数
  - [x] 1.3 pickle 结果写入不变

- [x] Task 2: Phase 1/2 合并为流水线
  - [x] 2.1 `pair_index` 映射 `(rev, fname)` → 版本对列表
  - [x] 2.2 `_dl_task` 返回 `(rev, fname, cache_path, ok)`
  - [x] 2.3 下载线程完成后 `_check_pairs` 检查双方就绪 → `pending_pairs`
  - [x] 2.4 主循环: 处理下载(fut.done()) → 启动子进程(pending_pairs) → poll子进程
  - [x] 2.5 提交参数改为路径 `(cur_path, prv_path, ...)` pickle <1KB
  - [x] 2.6 不再通过 `dl_cache` dict 缓存 bytes

- [x] Task 3: 语法验证 + graphify update
  - [x] `python -m py_compile` 两个文件均通过
  - [x] `graphify update` 成功

- [x] Task 4: 行为验证
  - [x] 单 worker (路径参数): 8 diffs, 11.3s ✓
  - [x] 2 worker 并发: 全部存活, 8+200 diffs ✓
  - [x] 4 worker 并发: 全部存活, 8+200+4+73 diffs ✓

# Task Dependencies
- Task 1 独立
- Task 2 依赖 Task 1
- Task 3 依赖 Task 2
- Task 4 依赖 Task 2
