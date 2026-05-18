# 策划工具箱 → 桌面 EXE 迁移 Spec

## Why
当前策划工具箱通过 VBS → web_launcher.py → Flask → 浏览器 运行，需要用户打开浏览器、手动管理窗口。改为独立 EXE 后可获得原生桌面体验：无边框窗口、屏幕贴边吸附、系统托盘、双击即用。

## What Changes
- **新增** `desktop_main.py`：桌面壳主入口（Flask 线程 + pywebview 窗口 + 贴边 + 托盘 + 单实例锁）
- **修改** `svn_oneclick_compare.py`：子进程启动统一用 `sys.executable` 替代硬编码 `"python"`
- **修改** `_cmp_worker.py`：适配打包模式下通过 `sys.executable --worker` 被调用
- **修改** `web_app.py`：注册 `--worker` CLI 参数 + worker 入口函数
- **修改** `toolbox_config.py`：打包模式下配置/缓存路径改为 `%APPDATA%/planning-toolbox/`
- **修改** `templates/index.html`：添加 `drag-bar` 拖拽区域 + sidebar padding-top 适配
- 打包后删除 `策划工具箱GUI.vbs`、`web_launcher.py`

## Impact
- Affected specs: (none, new capability)
- Affected code: `web_app.py`, `svn_oneclick_compare.py`, `_cmp_worker.py`, `toolbox_config.py`, `templates/index.html`
- New files: `desktop_main.py`

## ADDED Requirements

### Requirement: 桌面壳应用
系统 SHALL 提供一个 `desktop_main.py` 作为桌面壳入口，启动时自动完成 Flask 线程化、pywebview 窗口创建、贴边引擎启动、系统托盘初始化、单实例锁检查。

#### Scenario: 正常启动
- **WHEN** 用户双击 `desktop_main.py`（开发模式）或 `策划工具箱.exe`（打包后）
- **THEN** 系统创建无边框窗口（1100×700，居中），加载 Flask 后端页面 `http://127.0.0.1:18123`
- **AND** 系统托盘出现蓝色图标
- **AND** 窗口可拖拽移动、可缩放

#### Scenario: 重复启动
- **WHEN** 已有一个实例在运行
- **THEN** 新进程探测到端口 18124 被占用
- **AND** 新进程立即退出（不创建第二个窗口）

### Requirement: 子进程兼容
系统 SHALL 在打包为 EXE 后仍能正确启动 `svn_oneclick_compare.py` 和 `_cmp_worker.py` 作为子进程。

#### Scenario: EXE 模式下启动对比子进程
- **WHEN** 用户在 SVN 记录页签触发版本对比
- **THEN** `web_app.py` 通过 `subprocess.Popen([sys.executable, "svn_oneclick_compare.py", ...])` 启动子进程
- **AND** 子进程正常完成 Excel 下载/解析/对比
- **AND** 结果通过 SSE 流回前端

### Requirement: 配置路径适配
系统 SHALL 在打包模式下将配置文件 `svn_gui_config.json` 及所有缓存目录写入 `%APPDATA%/planning-toolbox/`。

#### Scenario: 打包模式下保存配置
- **WHEN** 用户在任一页签修改配置
- **THEN** 配置被持久化到 `%APPDATA%/planning-toolbox/svn_gui_config.json`
- **AND** 下次启动时正确读取

### Requirement: 无边框窗口拖拽
系统 SHALL 在 `templates/index.html` 的 `<body>` 顶部提供 32px 高的拖拽条（class `drag-bar pywebview-drag-region`），允许用户在无边框窗口中拖拽移动。

#### Scenario: 拖拽窗口
- **WHEN** 用户按住窗口顶部 32px 区域并拖动
- **THEN** 窗口随鼠标移动

### Requirement: 屏幕贴边吸附
系统 SHALL 在用户将窗口拖拽到屏幕边缘（左/右/上/下 40px 阈值内）且鼠标离开窗口后，自动将窗口滑入边缘，仅露出 4px 可见条。

#### Scenario: 贴边到右边缘
- **WHEN** 窗口右边缘距屏幕右边缘 ≤ 40px 且鼠标在窗口外
- **THEN** 窗口以 cubic ease 动画滑入，最终右边缘固定在 `SCREEN_W - 4px`
- **AND** 贴边引擎状态设置为 `docked = "right"`

#### Scenario: 鼠标唤醒滑出
- **WHEN** 窗口处于贴边状态且鼠标移到屏幕边缘 12px 触发区域
- **THEN** 窗口以 cubic ease 动画滑出到完全可见位置
- **AND** 贴边引擎状态清除

### Requirement: 系统托盘
系统 SHALL 提供 Windows 系统托盘图标（pystray），支持最小化到托盘和托盘右键退出。

#### Scenario: 关闭窗口到托盘
- **WHEN** 用户点击窗口关闭按钮
- **THEN** 窗口隐藏（不退出进程）
- **AND** 托盘图标保持可见

#### Scenario: 托盘恢复窗口
- **WHEN** 用户双击托盘图标或右键选择"显示窗口"
- **THEN** 窗口恢复显示并激活

#### Scenario: 托盘退出
- **WHEN** 用户右键托盘选择"退出"
- **THEN** Flask 线程终止
- **AND** 进程退出
