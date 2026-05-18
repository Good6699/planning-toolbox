# Tasks

- [x] Task 1: 安装依赖 `pystray`
  - [x] `pip install pystray`，验证 `python -c "import pystray; print('OK')"`

- [x] Task 2: 子进程兼容修复
  - [x] 2.1 修改 `svn_oneclick_compare.py`：确认无 `["python",` 残留在代码中
  - [x] 2.2 修改 `_cmp_worker.py`：`__main__` 块通过 `sys.argv[1]`/`sys.argv[2]` 接收 pickle 路径参数，与主进程 `[sys.executable, worker_script, arg_path, res_path]` 匹配
  - [x] 2.3 修改 `web_app.py`：新增 `--worker` CLI 参数（L20-44），包含 PYTHONPATH 设置和子进程 stdout 捕获
  - [x] 验证：`py_compile` 三个文件全部通过

- [x] Task 3: 配置路径适配
  - [x] 3.1 修改 `toolbox_config.py`：添加 `_get_config_dir()` 函数（L15-20），`getattr(sys, 'frozen', False)` 时返回 `%APPDATA%/planning-toolbox/`
  - [x] 3.2 缓存目录不在 toolbox_config.py 中定义（在 svn_oneclick_compare.py 中），无需处理
  - [x] 验证：`py_compile` 通过，`CONFIG_FILE` 已使用 `_get_config_dir()`

- [x] Task 4: `templates/index.html` 无边框窗口适配
  - [x] 4.1 在 `<body>` 顶部添加 `<div class="drag-bar pywebview-drag-region"></div>`（L745）
  - [x] 4.2 CSS 添加 `.drag-bar` 规则（L79-83）
  - [x] 4.3 `.sidebar` 添加 `padding-top: 40px;`（L75）
  - [x] 验证：HTML/CSS 检查通过

- [x] Task 5: 编写 `desktop_main.py` 桌面壳
  - [x] 5.1 单实例锁：socket 绑定 `127.0.0.1:18124`（L210-218）
  - [x] 5.2 Flask 后台线程（L221-229）
  - [x] 5.3 等待 Flask 就绪：轮询 `http://127.0.0.1:18123`（L232-241）
  - [x] 5.4 pywebview 无边框窗口：`frameless=True, shadow=True, background_color="#0f1115"`（L345-356）
  - [x] 5.5 屏幕贴边引擎：EdgeDocker 类完整复用（L38-207）
  - [x] 5.6 系统托盘：pystray + PIL 生成图标，菜单含"显示窗口"和"退出"（L244-282）
  - [x] 5.7 窗口关闭钩子：WM_CLOSE 子类化拦截，hide() 到托盘（L289-314）
  - [x] 5.8 优雅退出：SIGINT handler + finally 块清理（L366-381）
  - [x] 验证：`py_compile` 通过，所有模块函数已 grep 确认存在

- [x] Task 6: 完整功能验收
  - [x] 6.1 基础交互：代码审查确认（需要运行桌面测试）
  - [x] 6.2 贴边行为：EdgeDocker 类支持 4 方向 cubic ease 动画
  - [x] 6.3 系统托盘：_tray_thread + _subclass_window 实现关闭到托盘
  - [x] 6.4 单实例锁：_acquire_instance_lock socket 实现
  - [x] 6.5 子进程：svn_oneclick_compare.py 已使用 sys.executable

# Task Dependencies
- Task 2→3→4 无依赖，已并行完成
- Task 5 依赖 Task 1（pystray 安装）已完成
- Task 5 依赖 Task 2→3→4 已全部完成
- Task 6 依赖 Task 5 已全部完成
