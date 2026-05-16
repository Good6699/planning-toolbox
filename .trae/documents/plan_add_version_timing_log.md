# 计划：每个版本对添加解析时间日志

## 需求

在 `_process_one_pair` 的两个出口处，打印当前版本对的解析耗时。

## 改动点

`_process_one_pair` 中：

1. **函数开头**：`t0 = time.time()`
2. **全部跳过出口**（L2250）：日志改为 `_log(f"  对比进度: {dc}/{total_pairs}，{elapsed:.1f}s，全部跳过")`
3. **有差异出口**（L2321）：日志改为 `_log(f"  对比进度: {dc}/{total_pairs}，{elapsed:.1f}s，差异 {len(dr)} 条")`
4. **汇总段**（L2335+）：`total_elapsed = time.time() - phase2_t0`，改成 `min/sec` 格式汇总

## 涉及文件

| 文件 | 操作 |
|------|------|
| `svn_oneclick_compare.py` | 加 3 处计时 + 改 2 处日志格式 |
