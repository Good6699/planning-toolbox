---
name: "kill-all"
description: "一键关闭策划工具箱桌面端所有进程（Flask端口18123 + Python进程）。Invoke when user says '关闭'、'退出'、'杀掉'、'kill'、'关掉工具箱'、'停止'或端口被占用需要清理。"
---

# kill-all — 一键关闭所有桌面端进程

## 执行步骤

### Step 1: 查找并杀掉所有相关进程

```powershell
# 杀掉占用 18123 端口的进程（Flask 后端）
$ports = netstat -ano | Select-String ":18123" | ForEach-Object { $_ -split '\s+' | Select-Object -Last 1 }
if ($ports) { $ports | Select-Object -Unique | ForEach-Object { taskkill /PID $_ /F *>$null } }

# 杀掉所有残留的 Python desktop_main.py 进程
Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "desktop_main" -or $_.CommandLine -match "web_launcher" } 2>$null | ForEach-Object { taskkill /PID $_.Id /F *>$null }
```

### Step 2: 确认端口已释放

```powershell
netstat -ano | findstr ":18123.*LISTEN"
```

如果无输出，说明已完全关闭。

### Step 3: 汇报结果

- 输出每个被终止的 PID
- 如果端口未释放，提示用户手动检查

## 注意事项

- Python 进程可能以 `python.exe` 或 `pythonw.exe` 运行，两种都需要杀
- `desktop_main.py` 启动的 pywebview 窗口关闭后可能残留托盘进程，kill 进程组即可
- 如果先点了窗口关闭按钮（最小化到托盘），必须用本 Skill 才能彻底退出
