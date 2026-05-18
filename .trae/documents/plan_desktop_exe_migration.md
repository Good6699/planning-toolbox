# 策划工具箱 → 桌面 EXE 应用迁移计划

## 目标

将现有的 Flask + 浏览器 Web 版策划工具箱改造为独立桌面 EXE 应用，具备：
- pywebview 无边框桌面窗口（复用 Edge WebView2，零额外体积）
- QQ 式屏幕贴边吸附 + 鼠标悬停自动滑出/离开自动缩回
- 系统托盘图标（最小化到托盘、右键菜单退出）
- 单实例锁（重复双击 EXE 则激活已有窗口）
- 最终 Nuitka 编译为 ~50MB 单文件 EXE

---

## 架构对比

```
改造前：
  策划工具箱GUI.vbs → web_launcher.py → Flask web_app.py (端口 18123)
                                      → 浏览器打开 http://127.0.0.1:18123

改造后：
  策划工具箱.exe
    ├─ Flask 子线程 (web_app.py, 端口 18123, 仅监听 127.0.0.1)
    ├─ pywebview 无边框窗口 → http://127.0.0.1:18123 (Edge WebView2)
    ├─ 屏幕贴边引擎 (Win32 API, 后台定时器)
    ├─ 系统托盘 (pystray)
    └─ 单实例锁 (socket 端口占位)
```

---

## 需要新增/修改的文件

### 新增文件

| 文件 | 说明 | 预计行数 |
|------|------|----------|
| `desktop_main.py` | 桌面壳主入口：Flask 线程管理 + pywebview 窗口 + 贴边 + 托盘 + 单实例锁 | ~350 |
| `desktop_shell.spec` | Nuitka 打包配置（--onefile --windows-disable-console 等） | ~30 |

### 需要修改的文件

| 文件 | 改动内容 | 改动量 |
|------|----------|--------|
| `web_app.py` | 新增 `--worker` CLI 参数支持，让打包后的 EXE 也能通过 `sys.executable --worker ...` 启动子进程 | ~30 行 |
| `_cmp_worker.py` | 适配打包模式下的 `sys.executable` 路径解析 | ~10 行 |
| `svn_oneclick_compare.py` | 子进程启动时用 `sys.executable` 替代硬编码 `"python"` | ~5 行 |
| `toolbox_config.py` | 打包模式下配置路径改为 `%APPDATA%/planning-toolbox/` | ~15 行 |
| `templates/index.html` | 添加 `pywebview-drag-region` CSS class 用于自定义拖拽区域 | ~3 行 |

---

## 实施步骤

### 步骤 1：安装依赖

```powershell
pip install pywebview pywin32 pystray
```

验证：
```powershell
python -c "import webview; print('pywebview OK')"
python -c "import pystray; print('pystray OK')"
```

### 步骤 2：子进程兼容修复（先改后端，不改界面）

这是最关键的一步。当前 `svn_oneclick_compare.py` 和 `web_app.py` 中多处使用
`subprocess.Popen(["python", "xxx.py"])` 启动子进程。打包成 EXE 后没有独立的
`python.exe`。

**2.1 修改 `svn_oneclick_compare.py`**

定位所有 `subprocess.Popen([sys.executable, ...])` 或 `["python", ...]` 调用，
统一改为：
```python
subprocess.Popen([sys.executable, script_path, ...])
```
其中 `sys.executable` 在 EXE 模式下指向打包后的自身。

**2.2 修改 `_cmp_worker.py`**

确保它作为子进程被调用时能正确接收参数。当前通过 pickle 临时文件通信，
需要确认 `__main__` 块的参数解析逻辑。

**2.3 修改 `web_app.py` 中的子进程调用**

`web_app.py` 中 `_exec_export_text`、`_exec_upload_svn` 等函数通过
`subprocess.Popen(["cmd.exe", "/c", tool_path])` 启动外部 bat/exe，
这些不受打包影响，无需改动。

**验证**：先不打包，直接在命令行测试
```powershell
$env:PYTHONPATH="py_modules"; python web_app.py  # 确保后端正常运行
```

### 步骤 3：配置路径适配

修改 `toolbox_config.py` 中的 `CONFIG_FILE` 路径：

```python
import sys, os

def _get_config_dir():
    if getattr(sys, 'frozen', False):
        # PyInstaller / Nuitka 打包模式
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        d = os.path.join(base, 'planning-toolbox')
        os.makedirs(d, exist_ok=True)
        return d
    return SCRIPT_DIR  # 开发模式保持原路径

CONFIG_FILE = os.path.join(_get_config_dir(), 'svn_gui_config.json')
```

同理处理所有缓存目录（`__parse_cache__`、`__byte_cache__`、`__ss_cache__`）。

### 步骤 4：编写 `desktop_main.py` 桌面壳

这是核心新文件，包含以下模块：

**4.1 Flask 线程管理**
```python
def _start_flask():
    """在后台线程启动 Flask，端口 18123，仅监听 127.0.0.1"""
    from web_app import app
    app.run(host="127.0.0.1", port=18123, debug=False, use_reloader=False)
```

**4.2 pywebview 无边框窗口**
```python
window = webview.create_window(
    "策划工具箱",
    url="http://127.0.0.1:18123",
    width=1100, height=700,
    frameless=True,      # 无边框
    easy_drag=False,     # 自定义拖拽区域
    shadow=True,
    background_color="#0f1115",
    text_select=True,
)
```

**4.3 屏幕贴边引擎**

复用 [desktop_shell_demo.py](file:///c:/Users/admin/.qclaw/workspace/desktop_shell_demo.py) 中已验证的 `EdgeDocker` 类：
- `win32gui.GetWindowRect` 检测窗口位置
- 每 50ms tick 检测鼠标 → 窗口边缘关系
- 滑入/滑出 cubic ease 动画（18 帧 ~250ms）
- 支持右/左/顶/底四个方向

**4.4 系统托盘**
```python
import pystray
from PIL import Image, ImageDraw

def _create_tray_icon():
    icon = Image.new("RGBA", (32, 32), (0,0,0,0))
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle([4,4,28,28], radius=6, fill="#5ea2ff")
    return icon

tray = pystray.Icon("planning-toolbox", _create_tray_icon(),
                     menu=pystray.Menu(
                         pystray.MenuItem("显示窗口", _show_window, default=True),
                         pystray.MenuItem("退出", _quit_app),
                     ))
```

托盘行为：
- 关闭窗口 → 隐藏到托盘（不退出）
- 双击托盘图标 → 显示窗口
- 右键菜单 → 显示/退出

**4.5 单实例锁**
```python
import socket

_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _instance_socket.bind(("127.0.0.1", 18124))
except socket.error:
    # 已有实例在运行，发信号后退出
    sys.exit(0)
```

**4.6 启动流程**
```
desktop_main.py 启动
  ├─ 单实例锁检查 → 已存在则退出
  ├─ 启动 Flask 后台线程 → 等待 http://127.0.0.1:18123 就绪
  ├─ 创建系统托盘图标
  ├─ 创建 pywebview 窗口 → 加载 Flask URL
  ├─ 启动贴边引擎线程
  └─ webview.start() 进入 GUI 主循环
```

### 步骤 5：调整 `templates/index.html`

**5.1 无边框窗口拖拽适配**

在 `<body>` 顶部添加拖拽条：
```html
<div class="drag-bar pywebview-drag-region"></div>
```

CSS：
```css
.drag-bar {
  position: fixed; top: 0; left: 0; right: 0; height: 32px;
  z-index: 9999;
}
```

同时给侧边栏上方留出 32px 空白避免拖拽条遮挡：
```css
.sidebar { padding-top: 40px; }
```

**5.2 移除浏览器特定元素**

无需改动。现有 UI 已经适配深色主题，在 WebView2 中渲染效果一致。

### 步骤 6：完整功能测试

**6.1 基础功能**
- [ ] 窗口显示、拖拽、缩放
- [ ] 四个页签切换（SVN记录/上传SVN/工作流/翻译）
- [ ] 配置加载/保存（确认 %APPDATA% 路径）
- [ ] 贴边吸附 + 鼠标唤醒动画

**6.2 核心业务**
- [ ] SVN 版本对比流程（启动 → SSE 日志 → 结果）
- [ ] 文件上传流程
- [ ] 工作流执行流程
- [ ] 翻译 API 调用（SSE 日志 → 缓存命中率）

**6.3 系统交互**
- [ ] 关闭窗口 → 最小化到托盘
- [ ] 托盘双击 → 恢复窗口
- [ ] 托盘右键 → 退出
- [ ] 双击 EXE 第二次 → 激活已有窗口（不启动新实例）
- [ ] 贴边后鼠标移到边缘 → 滑出
- [ ] 鼠标离开窗口 → 滑回边缘

### 步骤 7：Nuitka 打包

**7.1 安装 Nuitka + C 编译器**

```powershell
pip install nuitka ordered-set zstandard
```
需要 Visual Studio Build Tools（C++ 编译器）。

**7.2 打包命令**

```powershell
python -m nuitka \
  --standalone \
  --onefile \
  --windows-disable-console \
  --windows-icon-from-ico=assets/icon.ico \
  --enable-plugin=anti-bloat \
  --include-package=flask \
  --include-package=webview \
  --include-package=win32gui \
  --include-package=lxml \
  --include-package=openpyxl \
  --include-data-dir=templates=templates \
  --include-data-dir=py_modules=py_modules \
  --output-filename=策划工具箱 \
  desktop_main.py
```

**7.3 预计输出**

| 指标 | 预期值 |
|------|--------|
| 编译时间 | 15-40 分钟 |
| EXE 大小 | 40-80 MB |
| 冷启动 | 1-3 秒 |
| 内存占用（空闲） | 50-80 MB |

---

## 技术风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| `svn_oneclick_compare.py` 子进程无法在 EXE 中启动 | 核心功能不可用 | 用 `sys.executable --worker` 模式让打包后的 EXE 自调用 |
| lxml C 扩展在 Nuitka 中兼容性 | 解析失败 | Nuitka 支持 C 扩展，lxml 有成熟打包先例 |
| Flask 依赖链复杂导致打包遗漏 | 运行时 ImportError | 用 `--include-package` 显式声明所有依赖 |
| Edge WebView2 在 Win7/8 未安装 | 窗口无法渲染 | 最小支持 Win10 1809+；如需要可内置 Evergreen Bootstrapper |
| pywebview 与新标签页 JS 冲突 | 页签切换异常 | `templates/index.html` 已经过浏览器验证，WebView2 行为一致 |

---

## 文件删除清单

打包上线后可以删除的旧文件（需要用户确认）：

| 文件 | 原因 |
|------|------|
| `策划工具箱GUI.vbs` | 被 desktop_main.py 取代 |
| `web_launcher.py` | Flask 线程化到 desktop_main.py 中 |

保留但不参与打包的文件：
- `desktop_shell_demo.py` — 原型文件，可保留作为参考

---

## 预计总工作量

| 步骤 | 时间 |
|------|------|
| 步骤 1-3：依赖安装 + 子进程兼容 + 配置路径 | 0.5天 |
| 步骤 4：desktop_main.py 编写 | 1天 |
| 步骤 5：index.html 微调 | 0.25天 |
| 步骤 6：完整测试 | 0.5天 |
| 步骤 7：Nuitka 打包调试 | 0.5天 |
| **合计** | **~2.75天** |
