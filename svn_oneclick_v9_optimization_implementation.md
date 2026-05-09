# SVN 对比工具 v9 性能优化实施报告

## 执行时间
2026-04-22 17:30

## 目标
解决 SVN 版本对比工具运行缓慢问题，从 ~120s 优化到 40-60s

## 问题诊断

### 原始日志分析
```
下载 40 个版本：~24s（0.6s/版本）
解析 32 对版本：~96s（3s/对）
总耗时：121s
```

### 根本原因
1. **假流水线**：代码注释说"并行下载 + 解析"，但 `dl_thread.join()` 在 Pool 启动前阻塞
2. **缓存未启用**：`_load_parse_from_disk()` 定义了但从未调用，每次都重新解析

## 实施方案（方案C：全部优化）

### 1. 启用缓存 ✅
- 添加 `_parse_excel_with_cache()` 函数
- 在 `_process_pair_worker_v2` 中使用缓存
- 进程内缓存 `_parsed_cache`（相同内容哈希直接返回）
- 添加缓存命中统计

### 2. 真流水线 ✅
- 移除 `dl_thread.join()` 阻塞
- 使用 `pool.imap_unordered()` + 生成器模式
- 下载线程 submit 任务 → Pool worker 立即消费
- 预计解析和下载重叠进行，节省 ~20s

### 3. 解析器优化 ✅
- 预编译正则 `_COL_RE`（提取列字母）
- 使用全局常量避免重复字符串拼接：
  - `_SHEET_TAG`, `_ROW_TAG`, `_CELL_TAG`, `_V_TAG`
  - `_SHEETDATA_TAG`, `_CELL_T_XPATH` 等
- 减少每次解析的内存分配

## 代码变更

### 文件
`C:\Users\admin\.qclaw\workspace\svn_oneclick_compare.py`

### 关键修改
1. 第 58-65 行：添加缓存统计变量
2. 第 339-365 行：预编译常量和正则
3. 第 763-795 行：新增 `_parse_excel_with_cache()`
4. 第 797-810 行：修改 `_process_pair_worker_v2` 使用缓存
5. 第 913-970 行：重写流水线逻辑（imap_unordered + 生成器）

## 预期效果

| 阶段 | 优化前 | 优化后（预计） | 提速 |
|------|--------|----------------|------|
| 下载 | 24s | 24s | - |
| 解析 | 96s | 40-60s | 40-60% |
| 总计 | 120s | 50-70s | 40-60% |

### 提速来源
1. **缓存命中**：相邻版本对可能共享相同内容，缓存命中可节省 30-50%
2. **流水线重叠**：下载和解析并行，节省 ~20s
3. **解析器优化**：减少字符串操作，提速 ~5-10%

## 测试建议
```bash
python svn_oneclick_compare.py --url http://192.168.1.41:8080/svn/D3/branches/20240606_KR2/gameData/Text/Texts.xlsm --start 2026-01-01 --end 2026-04-22 --output test_v9.xlsx --workers 6 --parse 8 --cmp-file Texts --title-rows 1 --id-col ::ID:: --output-cols ::ID::,::SC:: --keyword 裂隙
```

## 后续优化方向
1. 跨进程缓存：使用 `multiprocessing.Manager().dict()` 或 Redis
2. 更快的解析器：尝试 `openpyxl.read_only` 或 `pandas` 引擎
3. 增量对比：只解析差异单元格，不解析整个 sheet
