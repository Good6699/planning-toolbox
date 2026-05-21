---
name: "toolbox-run"
description: "启动、停止、重启 策划工具箱桌面版（pywebview + Flask）。Invoke when user asks to start/stop/restart the app, run the desktop, check status, or diagnose runtime issues."
---

# 策划工具箱 桌面版运行管理

## 🚀 一键重启

```powershell
# 杀掉旧进程 + 启动桌面版
$p = (netstat -ano | findstr :18123 | findstr LISTENING); if ($p) { $pid = ($p -split '\s+')[-1]; taskkill /PID $pid /F *>$null }; Start-Sleep 1; python desktop_main.py
```

## 项目结构

```
workspace/
├── desktop_main.py           # ⭐ 入口：pywebview 桌面壳 + 内嵌 Flask
├── 策划工具箱.bat             # 桌面快捷方式 → python desktop_main.py
├── 策划工具箱GUI.vbs          # VBS 桌面入口（双击 + 环境自动检测）
│
├── web_app.py                # Flask 后端（所有 API + 前端 SPA 路由）
├── templates/
│   └── index.html            # 前端界面（单文件 SPA）
│
├── toolbox_config.py         # 配置读写（svn_gui_config.json）
├── toolbox_platform.py       # 平台工具（_DropTarget 拖拽、子进程管理）
├── toolbox_tab_svn.py        # SVN 记录页签
├── toolbox_tab_upload.py     # 上传 SVN 页签
├── toolbox_tab_workflow.py   # SVN 工作流页签
├── toolbox_tab_translate.py  # 翻译页签
├── svn_compare_gui.py        # 旧版 tkinter 桌面入口（被 desktop_main.py 取代）
├── svn_launcher.py           # 旧版启动器
├── web_launcher.py           # 纯 Web 调试入口（浏览器访问，无 pywebview）
│
└── py_modules/               # 本地 Python 依赖
```

## 启动桌面版

### 方式 1: 一键重启（推荐）

```powershell
python desktop_main.py
```

- 架构：pywebview（WinForms）→ 内嵌 WebView2 → 加载 `http://127.0.0.1:18123`
- Flask 后端 `web_app.py` 自动随桌面壳启动
- 关闭窗口 → 最小化到系统托盘（非退出）
- 右键托盘图标 → 退出，完全终止进程

### 方式 2: 快捷方式

```
双击 策划工具箱.bat      → python desktop_main.py
双击 策划工具箱GUI.vbs    → VBS 环境检测 → pythonw.exe 静默启动
```

### 方式 3: 纯 Web 调试（无桌面壳）

```powershell
python web_launcher.py
```

- 浏览器打开 `http://127.0.0.1:18123`
- **没有** `pywebview.api`（浏览文件弹窗、拖拽 DnD 等不可用）
- 仅用于快速调试前端样式或后端 API

## 检查状态

```powershell
# 端口是否已占用
netstat -ano | findstr :18123

# HTTP 探活
curl -s http://127.0.0.1:18123/api/config
```

## 停止

### 正常退出
- 右键系统托盘图标 → 退出

### 强制终止（卡死 / 端口占用）
使用 **kill-all** Skill 一键关闭所有进程，或手动执行：
```powershell
$ports = netstat -ano | Select-String ":18123" | ForEach-Object { $_ -split '\s+' | Select-Object -Last 1 }
if ($ports) { $ports | Select-Object -Unique | ForEach-Object { taskkill /PID $_ /F *>$null } }
```

## 常见问题

### 页面加载但按钮点了没反应
- 确认运行的是 `desktop_main.py`（有 pywebview API），不是 `web_launcher.py`
- 打开浏览器 DevTools（F12）→ Console 看 JS 报错

### 模板修改后不生效
```powershell
# 重启即可，Flask TEMPLATES_AUTO_RELOAD = True
# 如果仍不生效，清理 WebView2 缓存：
# 桌面版按 Ctrl+Shift+R 或重启整个应用
```

### 浏览文件对话框 / 拖拽不工作
- 必须通过 `desktop_main.py` 启动，纯 Web 模式无 pywebview API
- 检查 `desktop_main.py` 的 `ResizeApi.browseFile()` 方法是否有异常

### Python 找不到模块
```powershell
python -c "import sys; print('\n'.join(sys.path))"
# 确认 workspace 和 py_modules 在 path 中
```

## 依赖
- Python 3.10+
- pywebview（桌面壳）
- Flask（后端 API）
- SVN 命令行工具（`svn` 在 PATH 中）
