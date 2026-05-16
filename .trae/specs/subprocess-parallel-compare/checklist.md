# Checklist

## Task 1: `_cmp_worker.py`

- [x] 脚本接收命令行参数（参数文件路径 + 结果文件路径）
- [x] pickle 正确序列化/反序列化
- [x] `import svn_oneclick_compare` 成功
- [x] `_cmp_task_proc` 调用正确
- [x] 异常退出 `sys.exit(1)` + stderr

## Task 2: Phase 2 subprocess 轮询

- [x] `subprocess.Popen` 启动独立 worker 进程
- [x] `max_workers = os.cpu_count()` 并发控制
- [x] `poll()` 轮询 + 结果读取 + 临时文件清理
- [x] 超时 120s kill
- [x] 结果合并逻辑不变

## Task 3: 语法验证

- [x] `python -m py_compile` 两个文件均通过
- [x] `graphify update` 成功

## Task 4: 行为验证

- [x] 单 worker 手动验证成功 (8 diffs, 11.2s)
- [x] 2 worker 并发全部存活、结果正确 (8+200 diffs)
- [x] 4 worker 并发全部存活、结果正确 (8+200+4+73 diffs)
- [x] 335 条差异结果不变（对比逻辑未改）
