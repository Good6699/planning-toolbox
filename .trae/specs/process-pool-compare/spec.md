# ProcessPool 并行对比 Spec

## Why
当前 Phase 2 使用 `ThreadPoolExecutor`，但由于 lxml `iterparse` 持有 GIL，8 个线程实际上串行执行解析。32 对 × 2 文件，仅 49 次全量解析就需 ~637s 硬下限。改用 `ProcessPoolExecutor` 后，每个进程有独立 GIL，N 个进程 = N 个 lxml 解析真正同时跑。

历史 v9/v10 失败是 Thread + Queue + Pool 混用导致的死锁/竞态，本次方案只用纯 ProcessPool，不存在竞态。

## What Changes
- `_zip_get_changed_sheets` 提取到模块顶层（Windows spawn 要求函数可 pickle）
- `_cmp_task` 提取到模块顶层，接收 `(cur_b, prv_b, cur, prv, fname)` 元组参数
- Phase 2 用 `ProcessPoolExecutor(max_workers=min(expected_pairs, os.cpu_count()))` 替代 `ThreadPoolExecutor`
- 子进程直接调 `_parse_excel_lxml` + `_compare_pair`（与当前 `_cmp_task` 逻辑完全一致）
- 主进程 `as_completed` 收集结果，逻辑不变
- **BREAKING**: 不再依赖 `_parsed_cache` / `_parse_cache_lock` / `_save_parse_to_disk`（子进程各自独立内存，无共享缓存）
- 不改 `_compare_pair` / `_dedupe_by_id` / `write_excel` / Phase 1

## Impact
- Affected specs: `independent-pair-compare`（继续不使用共享缓存），`smart-sheet-parsing`（only_sheets 继续生效）
- Affected code: `svn_oneclick_compare.py` — `_zip_get_changed_sheets` 提取到模块级，`_cmp_task` 提取到模块级，Phase 2 循环体

## ADDED Requirements

### Requirement: ProcessPoolExecutor 并行
Phase 2 SHALL 使用 `ProcessPoolExecutor` 替代 `ThreadPoolExecutor` 执行版本对对比。

#### Scenario: 16 进程并行 32 对
- **WHEN** `expected_pairs=32`, `os.cpu_count()=16`
- **THEN** `max_workers=16`
- **AND** 16 个 lxml 解析同时执行
- **AND** 每个进程有独立 GIL

#### Scenario: 子进程异常隔离
- **WHEN** 某个子进程的解析失败
- **THEN** 该异常只影响该进程
- **AND** 其他进程继续正常运行
- **AND** 主进程通过 `future.result()` 捕获异常后返回空结果

### Requirement: 模块级 task 函数
`_zip_get_changed_sheets` 和 `_cmp_task` SHALL 定义为模块顶层函数。

#### Scenario: Windows spawn 兼容
- **WHEN** 在 Windows 上运行
- **THEN** `multiprocessing` 使用 spawn 模式启动子进程
- **AND** 子进程重新导入模块
- **AND** `_zip_get_changed_sheets` 和 `_cmp_task` 在模块顶层可 pickle

### Requirement: bytes 直接传递
子进程 SHALL 通过 pickle 直接接收 bytes 数据，不使用临时文件。

#### Scenario: pickle 传参
- **WHEN** 主进程提交任务
- **THEN** `_cmp_task((cur_b, prv_b, cur, prv, fname))` 通过 pickle 序列化传参
- **AND** 不依赖 `dl_cache` 内存字典
- **AND** 不创建临时文件

### Requirement: 结果与 ThreadPool 一致
- **WHEN** ProcessPool 执行完成后
- **THEN** `diff_rows` 数量、内容与 ThreadPool 完全一致
- **AND** `all_file_results` / `file_header_data` / `file_sheet_order` 汇总逻辑不变

## MODIFIED Requirements
无。

## REMOVED Requirements
### Requirement: ThreadPoolExecutor Phase 2
**Reason**: GIL 使线程并行退化为串行，解析时间不变。
**Migration**: 替换为 ProcessPoolExecutor，收集结果逻辑不变。
