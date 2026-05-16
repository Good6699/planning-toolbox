# subprocess 并行对比 Spec

## Why
ProcessPoolExecutor 在 Windows spawn 模式下 2+ 进程会静默崩溃（实测：1 进程 OK，2 进程 worker1 消失）。根因是 `svn_oneclick_compare.py` 3000 行模块导入在 spawn 子进程中某处失败且未被捕获。

绕过方案：不用 `ProcessPoolExecutor` 管理子进程，而是为每个版本对启动独立的 `python.exe` 子进程（`subprocess.Popen`）。每个子进程是完全独立的 Python 解释器，无 spawn import 共享问题。实测 1 进程 7.5s 完成一对接入。

## What Changes
- 新增独立脚本 `_cmp_worker.py`：接收单对版本对比任务，调用 `_cmp_task_proc`，输出结果到临时文件
- 主进程 Phase 2 改用 `subprocess.Popen` 启动 N 个子进程，通过临时文件（pickle）传递参数和收集结果
- 并发数 = `min(expected_pairs, os.cpu_count())`，用 `Popen.poll()` 轮询控制
- 不改 `_cmp_task_proc` / `_parse_excel_lxml` / `_compare_pair` / `_zip_get_changed_sheets`
- Phase 1 下载、workbook 轻量解析不变

## Impact
- Affected code: `svn_oneclick_compare.py` — Phase 2 循环体；新增 `_cmp_worker.py`
- Affected specs: `ss-fingerprint-precheck`（继续生效），`independent-pair-compare`（子进程独立内存，本质延续）

## ADDED Requirements

### Requirement: subprocess 并行
Phase 2 SHALL 使用 `subprocess.Popen` 为每个版本对启动独立 Python 子进程。并发数 = `min(N, os.cpu_count())`。

#### Scenario: 32 对 16 并发
- **WHEN** 32 版本对, `os.cpu_count()=16`
- **THEN** `max_workers=16`
- **AND** 主进程轮询 `poll()` 等待子进程退出后启动新进程
- **AND** 每个子进程独立 lxml 解释器，GIL 不互斥，真正并行

#### Scenario: 子进程超时
- **WHEN** 某子进程超过 120s 未完成
- **THEN** `subprocess.kill()` 杀掉该进程
- **AND** 该对版本返回空结果（不阻塞整体）

#### Scenario: 子进程崩溃
- **WHEN** 子进程非零退出
- **THEN** 主进程记录错误并丢弃该对结果
- **AND** 继续处理剩余版本对

### Requirement: 参数通过临时文件传递
- `_cmp_worker.py` 从 pickle 临时文件读取 `(cur_b, prv_b, cur, prv, fname, tr, id_col, output_cols)` 参数
- 结果写入另一个 pickle 临时文件
- 主进程读取结果并删除临时文件

### Requirement: `_cmp_worker.py` 自包含
`_cmp_worker.py` SHALL 通过 `import svn_oneclick_compare` 引入所需函数，不做模块级副作用。

### Requirement: 结果与 ThreadPool 一致
- **WHEN** subprocess 并行执行完成后
- **THEN** `diff_rows` 数量、内容与 ThreadPool 完全一致
