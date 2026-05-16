---
name: "toolbox-run"
description: "启动、停止、诊断 策划工具箱 Flask 开发服务器。Invoke when user asks to start/stop/restart the server, run the app, check server status, or diagnose runtime issues."
---

# 策划工具箱 运行管理

## 项目结构

```
workspace/
├── web_launcher.py          # 入口：启动 Flask + 自动打开浏览器
├── web_app.py               # Flask 后端（所有 API）
├── templates/
│   └── index.html           # 单文件 SPA 前端
├── toolbox_config.py        # 配置读写
├── toolbox_platform.py      # 平台工具（子进程管理）
├── toolbox_tab_svn.py       # SVN Tab 后端逻辑
├── toolbox_tab_upload.py    # 上传 Tab 后端逻辑
├── toolbox_tab_workflow.py  # 工作流 Tab 后端逻辑
├── toolbox_tab_translate.py # 翻译 Tab 后端逻辑
├── 策划工具箱GUI.vbs         # VBS 桌面入口（双击启动）
└── py_modules/              # 本地 Python 依赖
```

## 启动服务器

### 方式 1: Python 直接启动（推荐开发时用）

```powershell
python web_launcher.py
```

- 端口: `18123`
- 地址: `http://127.0.0.1:18123`
- Flask debug=False，支持 `TEMPLATES_AUTO_RELOAD`
- 自动在 0.5 秒后打开浏览器

### 方式 2: VBS 桌面入口

```powershell
cscript 策划工具箱GUI.vbs
```

- 自动扫描文件系统中的 Python（含 py_modules）
- 运行 `setup_checker.py` 环境检查
- 以 pythonw.exe 无控制台模式启动

### 方式 3: 手动 Flask

```powershell
python -c "from web_app import app; app.run(host='127.0.0.1', port=18123, debug=True)"
```

## 检查服务器状态

```powershell
# 检查端口是否被占用
netstat -ano | findstr :18123

# 快速 HTTP 探活
curl -s http://127.0.0.1:18123/api/config
```

## 停止服务器

```powershell
# 找到 PID 并结束
$p = (netstat -ano | findstr :18123 | findstr LISTENING); if ($p) { $pid = ($p -split '\s+')[-1]; taskkill /PID $pid /F }
```

或者直接关掉运行 `web_launcher.py` 的终端窗口。

## API 速查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 渲染 index.html |
| GET | `/api/config` | 读取配置 JSON |
| POST | `/api/config` | 更新配置 |
| POST | `/api/browse` | 浏览文件夹对话框 |
| POST | `/api/svn/run` | 执行 SVN 任务 |
| POST | `/api/upload/list` | 列出上传目录文件 |
| POST | `/api/upload/run` | 执行上传任务 |
| POST | `/api/workflow/run` | 执行工作流任务 |
| POST | `/api/translate/run` | 执行翻译任务 |
| GET | `/api/task/<id>/stream` | SSE 日志流 |

## 常见问题诊断

### "端口被占用"
```powershell
netstat -ano | findstr :18123
# 找到 PID 后 taskkill /PID <pid> /F
```

### "页面加载但 API 无响应"
- 检查 `web_app.py` 是否正常运行
- 查看终端是否有 Python 报错
- 确认 `py_modules/` 里的 Flask 等依赖可用

### "模板修改后不生效"
- Flask 已设置 `TEMPLATES_AUTO_RELOAD = True`
- 如果仍不生效，手动重启服务器
- 清除浏览器缓存: Ctrl+Shift+R

### "Python 找不到模块"
```powershell
python -c "import sys; print('\n'.join(sys.path))"
# 确认 workspace 和 py_modules 在 path 中
```

## 依赖清单
- Python 3.10+
- Flask（`py_modules/` 内）
- 系统需有 SVN 命令行工具（`svn` 在 PATH 中）
