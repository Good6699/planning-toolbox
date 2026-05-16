# Checklist

## Task 1: `_cmp_worker.py` 路径参数

- [x] 参数元组改为 `(cur_path, prv_path, cur, prv, fname, tr, id_col, output_cols)`
- [x] 正确从路径读取 bytes
- [x] `_cmp_task_proc` 调用签名不变
- [x] pickle 结果写入不变

## Task 2: 流水线

- [x] `pair_index` 正确映射
- [x] 下载完成后 `_check_pairs` 检查双方就绪
- [x] 就绪对进入 `pending_pairs`
- [x] 主循环: 下载处理 + subprocess 启动 + poll
- [x] 提交参数改为路径（pickle <1KB）
- [x] `poll()` + 结果收集 + 临时文件清理逻辑不变
- [x] 不再通过内存 dict 缓存 raw bytes

## Task 3: 语法验证

- [x] `python -m py_compile` 两个文件均通过
- [x] `graphify update` 成功

## Task 4: 行为验证

- [x] 单 worker 路径参数验证成功 (8 diffs, 11.3s)
- [x] 2 worker 并发全部存活 (8+200 diffs)
- [x] 4 worker 并发全部存活 (8+200+4+73 diffs)
- [x] 335 条差异结果不变（对比逻辑未改）
