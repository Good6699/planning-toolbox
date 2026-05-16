# Phase 流水线 + 传路径 Spec

## Why
当前 Phase 1（下载 40 版本）与 Phase 2（16 子进程对比）**完全串行**：等全部下载完才开始解析。日志显示下载 5s 内首对版本的文件已就绪，浪费 25s。

同时当前通过 pickle 序列化 13MB raw bytes 写入临时文件，每对 1.5s 磁盘 I/O。字节缓存文件（`__byte_cache/{hash}_{rev}.bin`）已经在磁盘上，子进程可以直接读。

## What Changes
- **Phase 1/2 流水线**：下载线程完成一个版本 → 检查该版本所属的版本对是否双方都已就绪 → 是则立即启动子进程（不再等全部下载完）
- **_cmp_worker.py**：参数从 `(cur_b, prv_b, …)` 改为 `(cur_path, prv_path, …)`，子进程自己读缓存文件
- **BREAKING**: `_cmp_task_proc` 的 args tuple 格式不变（仍接收 bytes），改变仅在 worker 和主进程提交层
- 不改 `_parse_excel_lxml` / `_compare_pair` / `_zip_get_changed_sheets` / `_cmp_task_proc`

## Impact
- Affected specs: `subprocess-parallel-compare`
- Affected code: `svn_oneclick_compare.py` — Phase 1/2 合并为流水线循环；`_cmp_worker.py` — 参数反序列化改为读路径

## MODIFIED Requirements

### Requirement: 下载即提交流水线
Phase 1 下载线程 SHALL 在版本下载完成后立即检查其所属版本对是否双方均已就绪，就绪则立即提交子进程。Phase 2 不再等待 Phase 1 全部完成。

#### Scenario: 下载即提交
- **WHEN** 下载线程完成 rev 334431 的下载
- **AND** 版本对 (334431, 335136) 中 335136 也已完成下载
- **THEN** 立即启动 `_cmp_worker.py` 子进程处理该对
- **AND** 子进程与剩余下载并发执行

#### Scenario: 版本对未就绪则等待
- **WHEN** 下载线程完成 rev 334431 的下载
- **AND** 版本对 (334431, 335136) 中 335136 尚未下载
- **THEN** 该对不提交，等待 335136 下载完成时再触发

#### Scenario: 并发控制不变
- **THEN** `max_workers=os.cpu_count()` 限制同时运行的子进程数
- **AND** 如所有 worker 都在运行，新就绪的对进入待提交队列

### Requirement: 传路径代替 pickle bytes
`_cmp_worker.py` SHALL 接收缓存文件路径而非 raw bytes。参数元组为 `(cur_cache_path, prv_cache_path, cur, prv, fname, tr, id_col, output_cols)`。

#### Scenario: worker 从路径读取 bytes
- **WHEN** `_cmp_worker.py` 收到 `arg_file` 包含两个缓存文件路径
- **THEN** 子进程打开路径文件读取 bytes
- **AND** 传给 `_cmp_task_proc` 的 args 仍为 `(cur_b, prv_b, …)`（函数签名不变）

#### Scenario: 主进程 pickle 体积缩小
- **WHEN** 主进程提交一对任务
- **THEN** pickle 序列化内容为 2 个路径字符串 + 4 个 int + 1 个 str
- **AND** 序列化体积从 13MB 降至 <1KB

## REMOVED Requirements
无。
