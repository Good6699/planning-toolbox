# 优雅关闭与资源清理 Spec

## Why

web_app.py 和 svn_oneclick_compare.py 均无关闭清理机制。关掉 web / Ctrl+C / kill 进程时，子进程变孤儿继续占 CPU，临时文件残留在 %TEMP%，内存缓存和日志队列不释放。

## What Changes

- web_app.py：新增 signal handler，Flask 进程退出时终止所有子进程、清理 _log_queues
- svn_oneclick_compare.py：新增 atexit 钩子，确保主进程退出时 kill 所有对比子进程 + 清理临时文件
- 子进程超时/download 超时时显式 kill（修复已知遗漏）
- 对比流水线结束后主动清理 _parsed_cache 和 _byte_cache
- 提供 `/api/task/cancel` 端点中止正在运行的对比任务

## Impact

- Affected specs: 无现有 spec 受影响
- Affected code: web_app.py, svn_oneclick_compare.py, _cmp_worker.py, toolbox_tab_workflow.py

---

## ADDED Requirements

### Requirement: web_app 进程退出时清理子进程
系统 SHALL 在 Flask 进程收到 SIGTERM/SIGINT 时：
1. 终止所有通过 subprocess.Popen 启动的 SVN 子进程
2. 清理 _log_queues 字典
3. 在 5 秒内完成关闭

#### Scenario: Ctrl+C 中断正在运行的任务
- **WHEN** Flask 进程收到 SIGINT（Ctrl+C）
- **AND** 有 SVN 子进程正在运行
- **THEN** 所有子进程被 kill()
- **AND** _log_queues 被清空
- **AND** 进程退出

### Requirement: svn_oneclick_compare 进程退出时清理资源
系统 SHALL 注册 atexit 钩子，在进程退出时：
1. 遍历 running 字典中所有对比子进程，逐个 kill()
2. 遍历并 os.unlink() 所有 cmp_arg_*.pkl / cmp_res_*.pkl 临时文件
3. 调用 dl_ex.shutdown(wait=False) 关闭下载线程池（如果仍然存在）
4. 清空 _parsed_cache 和 _byte_cache 内存缓存

#### Scenario: 主进程在执行对比时被 kill
- **WHEN** 主进程收到 SIGTERM 或被 taskkill
- **AND** running 字典中有 4 个对比子进程
- **THEN** atexit 钩子 kill 所有 4 个子进程
- **AND** 清理对应的 8 个临时文件

### Requirement: 子进程超时显式 kill
系统 SHALL 在所有 subprocess.Popen/subprocess.run 调用中，当 TimeoutExpired 发生时显式调用 process.kill() 后 communicate() 收尸。

#### Scenario: 下载子进程超时
- **WHEN** _download_rev 或 _download_batch 的 communicate(timeout) 触发 TimeoutExpired
- **THEN** 子进程被 kill()
- **AND** communicate() 再次调用来回收僵尸

### Requirement: 对比任务结束后释放缓存
系统 SHALL 在 step3_download_and_compare 返回前：
1. 清空 _parsed_cache（已存在）
2. 清空 dl_cache_path 字典
3. 调用 gc.collect()

### Requirement: 任务取消端点
系统 SHALL 提供 `/api/task/cancel` POST 端点：
1. 根据 task_id 找到当前正在运行的对比任务
2. 终止所有相关子进程
3. 清理该任务关联的临时文件
4. 向 SSE 流推送 "任务已取消" 消息
5. 清理 _log_queues 中该 task 的条目

#### Scenario: 前端取消正在执行的对比任务
- **WHEN** 前端调用 POST /api/task/cancel {task_id: "xxx"}
- **AND** 该 task 有 4 个对比子进程正在运行
- **THEN** 所有 4 个子进程被终止
- **AND** SSE 流收到 {"type": "cancelled", "message": "任务已取消"}
- **AND** 临时文件被清理

### Requirement: download 子进程超时时 kill
修复 _download_rev (L1364) 和 _download_batch (L1403) 中 TimeoutExpired 被 catch 但不 kill 的问题。

#### Scenario: 下载超时
- **WHEN** _download_rev 的 communicate(timeout=180) 超时
- **THEN** process.kill() 被调用
- **AND** process.communicate() 被再次调用完成回收
- **AND** 返回 None（行为不变）
