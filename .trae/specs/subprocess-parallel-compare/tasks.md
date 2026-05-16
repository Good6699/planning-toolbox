# Tasks

- [x] Task 1: 创建 `_cmp_worker.py` 独立对比脚本
  - [x] 1.1 从 `sys.argv[1:]` 读取 arg_file + res_file
  - [x] 1.2 pickle 反序列化参数 → `_cmp_task_proc` → pickle 序列化结果
  - [x] 1.3 异常 → `sys.exit(1)` + stderr

- [x] Task 2: Phase 2 改用 `subprocess.Popen` 轮询并发
  - [x] 2.1 ThreadPoolExecutor → subprocess.Popen
  - [x] 2.2 tempfile + pickle 传递参数/结果
  - [x] 2.3 `max_workers = os.cpu_count()` 并发控制
  - [x] 2.4 `poll()` 轮询 + 120s 超时 kill
  - [x] 2.5 结果合并逻辑不变

- [x] Task 3: 语法验证 + graphify update
  - [x] `python -m py_compile` 两个文件均通过
  - [x] `graphify update` 成功

- [x] Task 4: 行为验证
  - [x] 单 worker: 8 diffs, 11.2s ✓
  - [x] 2 concurrent: 全部存活, 8+200 diffs ✓
  - [x] 4 concurrent: 全部存活, 8+200+4+73 diffs, 3.3x 加速 ✓

# Task Dependencies
- Task 1 独立
- Task 2 依赖 Task 1
- Task 3 依赖 Task 2
- Task 4 依赖 Task 2
