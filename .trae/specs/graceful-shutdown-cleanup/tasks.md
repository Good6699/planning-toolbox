# Tasks

- [x] Task 1: 修复 svn_oneclick_compare.py 下载超时不 kill 的 bug
  - [x] _download_rev 的 TimeoutExpired 分支增加 process.kill() + communicate()
  - [x] _download_batch 的 TimeoutExpired 分支增加 process.kill() + communicate()
  - [x] 验证: python -m py_compile svn_oneclick_compare.py

- [x] Task 2: svn_oneclick_compare.py 增加 atexit 资源清理钩子
  - [x] 注册 atexit 回调，遍历 _running_subprocesses 全局列表，逐个 kill() 子进程
  - [x] 清理 _pending_tempfiles 全局列表中的临时文件（os.unlink）
  - [x] 清空 _parsed_cache 内存缓存
  - [x] 调用 gc.collect()
  - [x] 对比流水线中将 Popen 对象和临时文件路径注册到全局列表
  - [x] 验证: python -m py_compile svn_oneclick_compare.py

- [x] Task 3: step3_download_and_compare 返回前释放缓存
  - [x] 确保 dl_cache_path 清空
  - [x] 确保 gc.collect() 已调用（已有，确认无遗漏）
  - [x] 验证: python -m py_compile svn_oneclick_compare.py

- [x] Task 4: web_app.py 增加 signal handler
  - [x] 新增 signal.signal(SIGTERM) 和 signal.signal(SIGINT) 处理器
  - [x] 处理器中终止 _active_subprocesses 列表中的所有子进程
  - [x] 处理器中清空 _log_queues
  - [x] 处理器中调用 sys.exit(0)
  - [x] 所有启动子进程的位置将 Popen 对象注册到 _active_subprocesses
  - [x] 子进程结束后从 _active_subprocesses 移除
  - [x] 验证: python -m py_compile web_app.py

- [x] Task 5: web_app.py 增加 /api/task/cancel 端点
  - [x] POST /api/task/cancel 接收 task_id
  - [x] 根据 task_id 找到对应子进程并 kill
  - [x] 清理 _log_queues 中该 task 条目
  - [x] 推送取消消息到该 task 的 SSE 流
  - [x] 验证: python -m py_compile web_app.py

- [x] Task 6: 端到端验证
  - [x] 三个文件 py_compile 全部通过
  - [x] 代码审查确认所有规范实现到位

# Task Dependencies
- Task 2 依赖 Task 1（共用 svn_oneclick_compare.py）
- Task 4, Task 5 可并行（均在 web_app.py 但功能独立）
- Task 6 依赖 Task 1-5
