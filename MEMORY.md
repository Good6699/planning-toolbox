- **2026-04-16**：记忆系统启用

## 技术规范偏好

- Windows批处理脚本开发中：使用UTF-8 with BOM格式解决中文乱码；注意enabledelayedexpansion与特殊字符(!)的冲突；set /p读取输入需处理引号；endlocal & set在for循环内会导致变量重置
- **批处理输入处理最佳实践**：用户输入可能包含引号，必须用 `for /f "delims=" %%a in ("!VAR!") do set VAR=%%~a` 去除；使用 `setlocal EnableDelayedExpansion` + `!VAR!` 语法避免特殊字符（& | < > ^）导致解析错误
- **批处理调试技巧**：闪退问题用`setlocal EnableDelayedExpansion`+分步echo定位；输入问题检查是否带引号；编码问题用Python生成`utf-8-sig`格式文件
- SVN工具开发偏好：Python脚本配合.bat启动器；使用PowerShell替代%date%获取日期以避免中文Windows系统格式问题；revision参数避免使用大括号{}以免被识别为日期格式
- Excel对比工作偏好：按行对比，关注ID和SC列的变化，操作类型区分为新增和修改
- 中文Windows批处理也可用纯GBK编码替代UTF-8（与代码页936一致），无需chcp 65001
- **2026-04-16**：记忆系统启用
- **2026-05-12**：桌面版UI全面重构 + 后端工作流接入
- **2026-05-20**：文件浏览全面改用 pywebview 原生对话框 + 工作流模态框自动保存

## 当前项目与关注

- **策划工具箱桌面版**：pywebview(内嵌WebView2) + Flask后端 + SPA前端，端口18123

## 策划工具箱桌面版架构

### 入口
```
策划工具箱.bat → desktop_main.py → pywebview(WinForms) → 内嵌WebView2加载 http://127.0.0.1:18123
                                  → 启动Flask后端(web_app.py, 端口18123)
                                  → 系统托盘(pystray)
```

### 后端 (`web_app.py`)
- Flask，端口18123，SSE日志流 `/api/log/stream/<task_id>`
- 路由清单：`GET /` `GET/POST /api/config` `POST /api/svn/run` `POST /api/upload/run` `POST /api/translate/run` `POST /api/workflow/run` `POST /api/files/list` `POST /api/dir/browse` `GET /api/log/stream/<id>` `GET /api/static/<path>`
- 工作流后端 `POST /api/workflow/run` 支持7种步骤类型：lock_svn/export_text/upload_svn/open_tables（已实现）、export_error_code/merge_translation/merge_table（需桌面版）
- SSE心跳15s，超时断开保护

### 前端 (`templates/index.html`)
- 单文件SPA：CSS变量 + HTML模板 + JS事件委托
- 四个页签：SVN记录/上传SVN/工作流/翻译

### CSS设计系统
- **8px网格**：所有尺寸只取4/8/12/16/20/24/32/40/48，禁止魔数
- **CSS变量**：`--space-xs/sm/md/lg/xl/2xl/3xl` `--btn-h:36px` `--btn-h-lg:42px` `--sidebar-width:260px`
- **根字号**：`font-size: 15px`（深色后台桌面工具基线）
- **统一class替代inline style**：`.card-header` `.card-header.compact` `.btn-sm` `.empty-state`
- **卡片间距**：仅靠grid gap `16px`，无margin-bottom
- **侧栏布局**：`minmax(0,1fr) 580px`（左侧弹性+右侧固定580px）
- **WF布局**：`320px minmax(0,1fr)`（左列表+右详情）
- **Workbench**：`repeat(auto-fit, minmax(360px, 1fr))`
- **日志**：`height: 320px` 固定，逐行渲染带时间戳+颜色标记
- **主按钮**：`260px × var(--btn-h-lg)`，`box-shadow` 发光效果
- **断点**：1200px Grid单栏，1000px sidebar折叠72px，900px sidebar水平全宽，1100px svn/upload/tr单列

### 已踩坑记录（UI相关）
- 禁止 `overflow:hidden` 在 html/body → 用 `overflow:auto;min-height:100%`
- 禁止 `.content` 设 `max-width` → 用 `.content-inner` 层居中包装
- 禁止 `minmax(大px值,Nfr)` 锁死最小宽度
- 禁止 card 同时用 grid gap 和 margin-bottom
- 禁止 inline style 硬编码 `height:2.25rem;margin-bottom:1rem;padding:3.75rem`
- 禁止 CSS zoom 属性
- 禁止 `flex-shrink:0` 搭配固定宽度
- 禁止 `-webkit-font-smoothing:antialiased` → Windows Chromium下文字发虚
- SVN地址下拉列表聚焦时显示全部缓存（非过滤匹配），打字时实时过滤
- saveConfig() 先更新本地config再发请求，避免竞态
- 配置从GitHub远程恢复（`svn_gui_config.json` 含7条SVN地址、7个工作流等）
- **工作流模态框浏览文件后自动保存**：2026-05-20 修复`browseFile()`/`browseDir()` 选完后只填值不保存的问题。在 pywebview API 分支设置 input value 后调用 `_wfModalAutoSave()`，立即保存并关闭弹窗
- **工作流模态框保存防重复**：`_wfModalDoSave()` 使用 `_wfSaving` 布尔锁防止 Enter 键或多次点击导致保存逻辑执行两次。`_wfSaving = true` 时直接 return，保存完成后重置为 false

### 核心文件位置

| 类别 | 文件 | 说明 |
|------|------|------|
| 桌面入口 | `desktop_main.py` | pywebview 桌面壳（`策划工具箱.bat` 启动） |
| 纯Web调试 | `web_launcher.py` | 浏览器直接访问，无 pywebview API |
| 后端 | `web_app.py` | Flask API + 路由 |
| 前端 | `templates/index.html` | 单文件 SPA |
| 配置 | `svn_gui_config.json` | 用户配置持久化 |
| 规范 | `.trae/skills/toolbox-ui/SKILL.md` | UI 开发规范 |
- 知识图谱：`graphify-out/`（`graphify_quick.py --no-viz` 增量更新）

## 经验与决策

- svn cat 替代 svn export 可直接读入内存，提升SVN导出速度
- svn diff --summarize 可先判断版本间文件差异，避免对无变化文件做完整export
- **多进程解析Excel**：openpyxl read_only模式 + ProcessPoolExecutor 并行解析，比串行pandas快30倍
- **下载/解析流水线**：下载批次后立即提交解析任务，不等待全部下载完成，总时间=max(下载,解析)而非相加
- **ID Map缓存**：对比阶段预构建ID→SC映射并缓存，避免每次对比都重建，对比提速约50%
- **pywebview 文件浏览最佳实践**：
  - 在 pywebview(WebView2) 中，`<input type="file">` 的 `file.path` 属性不可用（非标准扩展），fallback 到 `file.name` 导致只能获取文件名，完整路径丢失
  - 正确做法：通过 `window.pywebview.api`（JS-Python 桥）调用 Python 端的 `ResizeApi` 方法，Python 端再调用 `window.create_file_dialog(webview.OPEN_DIALOG, ...)` 打开原生 Windows 文件对话框，返回的路径是完整的绝对路径
  - 文件类型格式必须为 `('Description (*.ext)', ...)` 字符串元组，不是 `[('Description', '*.ext')]` 列表
  - 目录选择：`window.create_file_dialog(webview.FOLDER_DIALOG)` → 返回 `tuple[str]`（选中文件夹的完整路径）
  - JS 侧调用方式：`const path = await window.pywebview.api.browseFile()`，path 为完整绝对路径
  - 路由对应：`create_file_dialog` 是 `Window` 实例方法，必须通过 `webview.windows[0]` 获取窗口实例调用
  - `webview.OPEN_DIALOG` 和 `webview.FOLDER_DIALOG` 是模块级常量，均存在
- **工作流模态框浏览按钮修复**：2026-05-20 工作流步骤设置弹窗的"浏览"按钮无法触发文件对话框。根因：① `_fb()` 模板中的 `file_types` 传了 `[('Excel Files', '*.*')]`（元组列表），pywebview 要求 `('Excel Files (*.xlsm)', ...)`（格式化字符串），导致 `parse_file_type` 抛出 ValueError 并被 `except Exception: pass` 吞掉；② `addEventListener` 在 WebView2 模态框 overlay 中不触发，改为 `onclick` IIFE 直接绑定。涉及文件：`desktop_main.py`（file_types 格式 + 异常打印）、`index.html`（按钮绑定改为 onclick 内联 IIFE）
- **浏览对话框初始目录**：2026-05-20 点击"浏览"时，文件对话框默认打开输入框中已有路径的父目录，而不是系统"最近使用的目录"。`ResizeApi.browseFile(directory)` 和 `browseDir(directory)` 接受 `directory` 参数传给 `create_file_dialog`；前端 IIFE 从 input value 中提取路径（file 类型截取 `lastIndexOf('\')` 父目录），JS 端传给 `pywebview.api.browseFile(initialDir)`。涉及文件：`desktop_main.py`（directory 参数）、`index.html`（IIFE 传初始路径 + browseFile/browseDir 形参）
- **全局函数不能调用闭包内函数**：2026-05-20 `browseFile()` 是全局函数，调用 `_wfModalAutoSave()` 时报 `is not defined`，因为它是工作流页签闭包内的局部变量。修复：`window._wfModalAutoSave = _wfModalAutoSave` 暴露到 window 对象；调用处 `window._wfModalAutoSave()` 并加 `typeof` 安全判断。经验：通过 `window.xxx` 将闭包内函数暴露为全局，是 pywebview JS 桥调用闭包变量的标准做法
- **合并翻译工作流支持**：2026-05-20 `web_app.py` 中 `_exec_merge_translation` 从仅打印"合并翻译功能请使用桌面版"的桩函数替换为完整的合并翻译逻辑（读取翻译文件 → 按 ID 匹配 → 差异对比 → VBScript 写入原文件）。涉及文件：`web_app.py`（新增大约 250 行实现）、`xlsm_zipper.py`（已有）
- **合并翻译跳过中文列**：2026-05-20 合并翻译时会把所有语言列都写入原文件，导致中文列也被覆盖。第1版：硬编码中文列名列表；第2版（修正）：从`svn_gui_config.json`的`tr_lang_id_map`加载语言配置，筛选出所有key含"中文"、"chinese"的语言对应的ID标识符集合，用该动态集合代替硬编码列表跳过中文列。如果语言配置为空则 fallback 到硬编码列表。涉及文件：`web_app.py`、`toolbox_tab_workflow.py`
- **导出错误码工作流支持**：2026-05-20 `web_app.py` 中 `_exec_export_error_code` 从仅打印"导出错误码功能请使用桌面版"的桩函数替换为完整实现（解析根目录 → 查找 Language 目录 → 遍历语言代码 → 调用 ExcelTool2.py 导出）。涉及文件：`web_app.py`
- **上传SVN流程统一改为 TortoiseSVN 手动提交**：2026-05-20 ① 工作流 `upload_svn` 去掉 `svn update` 操作，之前 workflow 会先用 `svn update --accept theirs-full` 更新目录再弹 TortoiseSVN；② 上传SVN页签改为先 `svn update` 再弹 TortoiseSVN，删除了原有的自动 `svn add + svn commit` 备选路径（`_show_svn_confirm_dialog` 和 `_do_svn_commit` 两个方法共约 160 行），未安装 TortoiseSVN 时直接提示报错。涉及文件：`web_app.py`（删 svn update）、`toolbox_tab_upload.py`（加 svn update + 删自动提交）
- **pywebview 拖拽修复**：2026-05-20 `_init_dnd()` 中当 pywebview drop event 的 `target_id` 为空时，fallback 到 JS 侧 `_lastDropTargetId` 变量（在 `enablePathDrop` 中记录的 hover input id），修复 modal 弹窗内拖拽无法识别目标 input 导致路径没保存的问题；同时 `blur` → `change` 事件确保拖拽后能正确触发保存
- **文档清理**：2026-05-20 将 `AGENTS.md` 和 `MEMORY.md` 中的"Web版"独立版本概念全部清理，统一为"桌面版唯一版本，web_app.py 是其内置后端"；`desktop_main.py` 为入口，`web_launcher.py` 仅为调试工具
- **toolbox-run Skill 改桌面版**：2026-05-20 一键重启改为 `python desktop_main.py`，项目结构以 `desktop_main.py` 为首，停止方式增加托盘退出说明
- **Windows批处理编码陷阱**：
  - `write` 工具默认写入UTF-8无BOM，中文Windows批处理必须用Python以`utf-8-sig`格式写入
  - 通过管道执行批处理时（如`echo input | script.bat`），反斜杠会被当作转义符，导致`\.q`被解析为命令
  - 用户输入常带引号（如`"2.txt"`而非`2.txt`），必须用`for /f`循环去除，简单的`%VAR:"=%`不够可靠
- svn info返回的URL是编码后的中文路径，需用urllib.parse.unquote解码
- Texts.xlsm 的 header 列名是 ::ID:: 和 ::SC::（带 :: 前后缀），列名匹配必须包含 ::ID:: 和 ::SC:: 才能正确识别
- **Windows文件名禁止冒号**：cache_key拼入 `::ID::` 等含冒号的列名后作为文件名，Windows拒绝创建（`OSError [Errno 22]`），必须用 `_safe_cache_key()` 替换非法字符。`except: pass` 吞掉此类异常会导致缓存永远为空且无报错。
- **多进程IPC开销**：worker返回parsed dict（18MB/个），32个pair需传1.15GB数据到主进程，严重影响性能。应让worker直接写磁盘缓存，只返回轻量结果（diff_rows + 元数据）。
- **`_cache_hits/_cache_misses` 计数器在worker进程递增但不回传主进程**，导致主进程的缓存统计永远为0不打印

### ctypes 窗口子类化：64位Windows下必须用 wintypes 类型
- **场景**：`desktop_main.py` 中 `_subclass_window()` 和 `_fallback_subclass()` 使用 ctypes 对 pywebview 窗口做窗口过程子类化，实现隐藏到托盘和任务栏激活
- **根因**：① HWND/WPARAM/LPARAM 在64位Windows上是指针尺寸（64位），必须用 `wintypes.HWND`/`wintypes.WPARAM`/`wintypes.LPARAM`，不能用 `c_longlong`。用整数类型时，ctypes 做的是有符号整数转换，某些高位指针地址（如 `0x7FFE...`）会被截断或溢出；② `SetWindowLongPtrW` 的 `argtypes` 未设置或类型不匹配时默认按 `c_int`（32位）传参，函数静默失败返回0；③ `_fallback_original=0` 时 fallback 回调跳过 `CallWindowProcW` 直接走 `DefWindowProcW`，绕过了 WinForms 内部消息泵，窗口卡死
- **解决方案**：① 用 `ctypes.WinDLL('user32', use_last_error=True)` 创建独立 DLL 实例（避免与全局 `ctypes.windll` 冲突）；② `argtypes` 全部使用 `wintypes.HWND`、`wintypes.UINT`、`wintypes.WPARAM`、`wintypes.LPARAM`、`ctypes.c_void_p`（函数指针）；③ 调用 `SetWindowLongPtrW` 前后检查 `ctypes.get_last_error()` 确认返回值是否有效（返回0不一定表示失败，原始值可能为0，需配合 `SetLastError(0)` + `GetLastError()` 判断）；④ 回调函数返回值类型用 `ctypes.c_longlong`（LRESULT 在 64 位下为 64 位有符号）
- **涉及文件**：[desktop_main.py](file:///c:/Users/admin/.qclaw/workspace/desktop_main.py)

### SVN 精准文件合并功能
- **场景**：新增第5个页签"SVN合并"，实现双SVN地址输入→筛选版本→选择文件→执行合并→唤起提交弹窗的完整流程
- **设计**：独立模块 `toolbox_merge.py`（SVN log查询、diff分析、文件级merge、TortoiseSVN弹窗）+ Flask API 端点 + SPA前端页签
- **关键点**：① 文件级合而不是项目级合并，逐文件调用 `svn merge --accept theirs-full -c REV URL FILE`；② 冲突处理统一用 `theirs-full`，无需人工确认；③ 复用已有 SSE 日志流模式；④ 合并完成后自动唤起 TortoiseSVN 提交弹窗
- **涉及文件**：[toolbox_merge.py](file:///c:/Users/admin/.qclaw/workspace/toolbox_merge.py)（新增）、[web_app.py](file:///c:/Users/admin/.qclaw/workspace/web_app.py)、[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### JS 可选链不能用于赋值左侧
- **场景**：`index.html` 中 `runMergeRun()` 的 `sb?.querySelector("span")?.textContent = "系统空闲"` 导致整个 `<script>` 块解析失败
- **根因**：JS 的 `?.` 可选链操作符是表达式（产生值），不能用作赋值目标。`OptionalExpression = value` 是 `SyntaxError: Invalid left-hand side in assignment`，会导致整个页面 JS 全部不执行（侧边栏、导航全部消失）
- **解决方案**：改用 `if (sb) { sb.classList.remove("running"); ... }` 安全守卫
- **涉及文件**：[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### 严格禁止修改与当前功能无关的文件
- **场景**：在实现SVN精准文件合并功能时，"顺手"修改了 `desktop_main.py` 的 ctypes 窗口子类化参数类型（`c_longlong` → `wintypes`），导致窗口拖动闪现和关闭按钮异常
- **根因**：违反了"只改用户指定的部分，其他保持原样"的纪律。`desktop_main.py` 的窗口子类化在原始版本中工作正常，无需改动。修改一个非目标文件引入了两个新 bug（拖拽闪现 + 关闭异常），调试时间远超 SVN 合并功能本身的开发时间
- **解决方案**：用 `git checkout <正常版本> -- desktop_main.py` 恢复文件到原始版本。窗口拖拽闪现 bug 在原始代码中已存在（`SetWindowLongPtrW` 未设 `argtypes` 导致 64 位指针截断），不是本次功能引入
- **涉及文件**：[desktop_main.py](file:///c:/Users/admin/.qclaw/workspace/desktop_main.py)
- **教训**：修改代码前必须先 `git diff` 确认当前修改仅涉及目标文件。发现任何非目标文件在 diff 中出现时立即停止

### svn log --verbose 文件路径格式与 URL pathname 不一致
- **场景**：实现语义合并页签的文件排除功能时，新增 `_isFileUnderSourceUrl()` 尝试仅显示当前 SVN URL 下的文件
- **根因**：`svn log URL --verbose --xml` 返回的 `<path>` 内容是以仓库根为基准的路径（如 `/branches/xxx/Assets/file.txt`），而 `new URL(sourceUrl).pathname` 包含 SVN 服务的仓库挂载路径（如 `http://svn/repo/branches/xxx` → pathname `/repo/branches/xxx`）。两者路径前缀不同，导致所有文件都被过滤掉，文件列表为空
- **解决方案**：完全移除 `_isFileUnderSourceUrl()`。`svn log URL --verbose` 本身就已经只返回该 URL 范围内的文件，无需额外过滤
- **涉及文件**：[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### 设置按钮/配置UI必须始终可见，不应依赖数据状态
- **场景**：变更文件列表的"⚙ 排除设置"按钮放在 `merge_file_footer` 中，footer 初始带 `merge-ops-hidden`，只有文件列表有内容时才显示
- **根因**：用户需要在勾选版本/显示文件之前就能配置排除规则，数据驱动的可见性逻辑导致设置按钮不可达
- **解决方案**：将 footer 改为始终可见（去掉 `merge-ops-hidden`），仅隐藏内部的计数文字；`_refreshMergeFileList()` 不再控制 footer 显示/隐藏
- **涉及文件**：[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### merge_target_history 配置白名单缺失导致重启后丢失
- **场景**：`#merge_target` 输入框 blur 时已正确保存 `merge_target_history` 到 JSON 文件，但重启后历史记录消失
- **根因**：Flask 的 `GET /api/config` 使用白名单返回配置，`merge_target_history` 不在白名单中（仅 output_dir_history / svn_keyword_history 等历史字段在白名单中），导致前端 `config.merge_target_history` 为 `undefined`
- **解决方案**：
  1. 在 `web_app.py` 的 `safe` 字典中添加 `"merge_target_history": cfg.get("merge_target_history", [])`
  2. 在 `_selectSuggest()` 的 `_configMap` 和删除建议项的 `map` 中补充 `merge_target` / `merge_author` / `merge_keyword` 的配置键映射，确保从下拉列表选择/删除时也持久化排序
- **教训**：新增配置键时，必须同时检查前端的 blur 保存逻辑 + 后端的 GET 白名单。POST 写入没问题不代表 GET 读回没问题。
- **涉及文件**：[web_app.py](file:///c:/Users/admin/.qclaw/workspace/web_app.py)、[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

## 行为准则

- **严标按用户指令行事，不自由发挖。** 用户的每个字是意图，不猜测、不延伸、不加戏。有疑问先问。
- **每次做任务前，先完整核对再动手。** 不在未经用户确认的情况下直接实现功能。
- **拆分为最小子任务，每完成一个子任务立即找用户确认。** 拆分到不可再分为止，确认完一个再做下一个，不批量交付。
- **设计方案以效率优先。** 在多个可行方案中选运行效率最高/性能最优的那个，不追求"完美"方案。
- **修改代码时，不改变原有的逻辑和表现。** 只改用户指定的部分，其他保持原样。不要"顺手优化"或"顺便重构"。
- **修改代码后，检查关联功能是否有影响。** 修改任何函数、方法或属性时，必须搜索整个项目中所有使用该名称的地方，确保命名一致、调用方式正确。
- **边界判定问题先确认。** 遇到日期范围、临界值、逻辑可能有歧义的问题时，先与用户确认再修复，不要自行假设。
- **每次修改文件后必须跑这3步，不跳步**：①改代码 → ②node语法检查 → ③graphify update。2026-05-10因漏跑graphify导致知识图谱落后于代码，教训：复杂重构时注意力集中在逻辑上容易跳过收尾步骤，必须用原子化流程防遗漏。
- **解决问题前先查网络和Skill**：接到技术问题后，先用WebSearch查网上有没有更好的方案、库、工具，再用Skill工具查看是否有匹配的技能可用，最后综合外部信息+项目现有代码给出方案。不要闭门造车。

## 外部研究知识（2026-05-20 整理）

### pywebview 桌面开发
- **渲染器选择**：Windows 下优先使用 Edge Chromium（自动检测），比 MSHTML 性能好、支持硬件加速。项目当前 `desktop_main.py` 未指定 gui 参数，pywebview 会自动选 edgechromium
- **create_file_dialog 返回值**：`OPEN_DIALOG` 返回 `tuple[str]`（选中文件路径），`FOLDER_DIALOG` 同样返回 `tuple`。Windows 下返回类型与 macOS 不同（Win 返回字符串，macOS 返回 tuple），pywebview 5.x 已统一为 tuple
- **JS-Python 桥线程安全**：`js_api` 暴露的函数在**独立线程**中执行，不是主线程。多个 JS 调用可并发执行，需要在 Python 侧加锁保护共享数据
- **窗口事件**：`events.loaded`（页面加载完）适合绑定 DOM 事件，`events.shown`（窗口显示）适合操作窗口 HWND
- **WebView2 启动优化**：首次启动较慢（冷启动），因为 Chromium 需要创建子进程。项目已通过 Flask 预热 + pywebview 内嵌 url 缓解。WebView2 运行时版本需 ≥ 86.0.622.0
- **AllowDrop 冲突**：pywebview WinForms 默认启用 WebView2 的 AllowDrop，与自定义 DnD 冲突。项目已通过 `wv.AllowDrop = False` 关闭

### Flask SSE 长连接
- **连接断开检测**：客户端断开时 Flask 生成器会收到 `GeneratorExit` 异常（不总是可靠），更可靠的方法是用 `request.is_disconnected()` 轮询
- **心跳机制**：每 15-30s 发一条 `: heartbeat\n\n` 注释行，防止反向代理（Nginx）超时断开连接。项目当前心跳 15s 合理
- **queue.Queue 模式**：每个 SSE 连接使用独立 `queue.Queue`，后台任务 `put()` 事件，SSE 生成器 `get(timeout=...)` 消费。用 `threading.Lock` 保护 `_log_queues` 字典
- **不依赖 Redis**：单实例场景直接用 Python `queue.Queue` 即可，不需要 Redis pub/sub。项目当前的模式（`_log_queues[task_id]` 字典 + queue）是标准做法
- **连接清理**：Flask 开发服务器不支持长连接高并发，但桌面版单用户场景没事。注意 `finally` 块必须从 `_log_queues` 移除已断开连接的队列

### openpyxl 大文件处理
- **read_only 模式**：`load_workbook(read_only=True)` 按行流式读取，内存从几百MB降到 ~50MB。项目已全面使用
- **lxml 加速**：安装 `lxml` 后 openpyxl 自动使用它做 XML 解析，比标准 xml.etree 快 2-3 倍。项目已依赖 lxml
- **data_only 模式**：`load_workbook(data_only=True)` 读取公式计算结果而非公式本身。写入后重新打开需确保文件已保存
- **write_only 模式**：创建大文件用 `Workbook(write_only=True)`，追加行用 `ws.append()`，内存恒定。注意 write_only 不支持修改已有文件
- **close() 必须调**：read_only 模式打开的文件必须调 `wb.close()` 释放文件句柄，否则文件被锁定。项目代码中 `_cmp_worker.py` 已在用 `try/finally` 确保关闭

### subprocess Windows 最佳实践
- **隐藏控制台窗口**：`STARTUPINFO(dwFlags=STARTF_USESHOWWINDOW, wShowWindow=SW_HIDE)` + `creationflags=CREATE_NO_WINDOW`。项目 `_get_subprocess_kwargs()` 已正确实现
- **communicate() 防死锁**：`Popen` 用 `stdout=PIPE` 时，如果父进程不读输出而子进程写满管道 buffer（默认 64KB），子进程会阻塞死锁。必须用 `proc.communicate()` 或逐行读取。项目已使用 `iter(proc.stdout.readline, "")` 逐行读取
- **编码问题**：Windows 控制台默认编码可能是 GBK（cp936）或系统 OEM 编码。`subprocess.Popen` 用 `text=True, encoding="utf-8", errors="replace"` 自动处理。如果子进程输出 GBK 编码，需指定 `encoding="gbk"`
- **进程泄露预防**：`Popen` 对象在 `with` 语句中使用（`with Popen(...) as proc:`），退出时自动关闭管道。使用 `preexec_fn`（POSIX）或 `creationflags`（Windows）确保子进程不继承父进程句柄

### SPA 前端开发通用建议
- **事件委托**：项目已使用事件委托模式（`panel.querySelectorAll("button,input").forEach(el => el.addEventListener(...)）`），避免动态元素重复绑定
- **配置状态管理**：项目使用全局 `config` 对象 + `saveConfig()` 的"先改本地再发请求"模式，避免了请求竞态——这是正确的做法
- **CSS 设计系统**：CSS 变量 + 8px 网格 + 统一 class 替换 inline style，项目已在使用，继续保持
- **深色主题**：Windows Chromium 下不要用 `-webkit-font-smoothing: antialiased`（已踩坑），使用默认字体渲染

### Excel 对比（xlsm 格式）
- **sharedStrings 解析**：ss.xml 可能非常大（24万条），纯正则 `_SS_TEXT_RE` 比 lxml iterparse 快且内存低。项目已使用纯正则
- **xlsm 是 zip 包**：直接用 `zipfile` 操作 .xlsm 文件，无需解压。项目 `_cmp_worker.py` 已用 `zipfile.ZipFile` 读取
- **ID 列作为唯一键**：使用 `::ID::` 列作为行标识（带::前后缀）。项目已确认此命名规则

## Excel 对比工具核心问题 (2026-05-14)

### 指纹不能精准筛选表格变化

**问题**：使用 sharedStrings 索引计算指纹，无法精确识别以下变化：
- 同一索引指向不同文本
- 不同类型但值相同的 cell
- 文本内容的实际变化

**解决方案**：改用 cell 原始内容计算 Hash
- Sheet 级：`ref:v:type` 三元组 MD5
- 行级：`ref:v:type` 格式
- 不再依赖 sharedStrings 解析

**代码变更**：
- `_compute_sheet_content_fp` → `_compute_sheet_content_hash(raw)`
- `_compute_row_fingerprint` → `_compute_row_content_hash(row_xml)`

### 关键配置
- Texts.xlsm 使用 `output_cols = ["::ID::", "::SC::", "SubstituteId"]`
- ID 变更回退逻辑需要始终执行（不能被 `not output_cols` 条件跳过）

### 性能瓶颈
- SS 解析（24万条）耗时占比 80%+
- 优化方案：预解析阶段提前解析 sharedStrings 到缓存

---

## 2026-05-10 自动化答题+学习脚本开发

### 网站
`https://scit-adult-study.whxunw.com` 四川工业科技学院成人教育管理平台（Vue.js + Element UI）

### 答题脚本 (`自动学习/auto_exam.js`)
两阶段策略：
1. **Phase 1**: 遍历"开始作业"/"继续作业" → 空提交 → 全部变为"查看作业"
2. **Phase 2**: 按固定索引取"查看作业" → 从 HTML 正则提取 `试题答案:<span>X</span>` → 回列表按同索引取"重做" → DOM click radio → 提交

关键经验：
- **WeakSet 不可用于去重 DOM**：`querySelectorAll` 每次返回新引用，`has()` 永远 false。改用索引计数或 `nthBtn(text, n)`
- **Element UI radio 需逐一点击**：间隔 150-300ms，不能 forEach 一次性全点
- **`vm.submit()` 不可靠**：应通过 DOM 按钮 `button.innerText === '提交'` 触发

## 2026-05-21 桌面端子类化 + 工作流UI + flake8清理

### 子类化 fallback 路径 DefWindowProcW 参数溢出
- **根因**：ctypes windll 的 `DefWindowProcW`/`CallWindowProcW` 未设置 `argtypes`，默认用 `c_int`（32位）传参，64位 Windows 上 `lparam` 包含指针值时必然溢出。`SetWindowSubclass` 失败后走 fallback 路径（`SetWindowLongPtrW`），但 fallback 代码也忘了设 `argtypes`。
- **解决方案**：在 `_fallback_subclass` 中 `_wnd_proc` 定义前补充两行 `argtypes`：`DefWindowProcW = (c_longlong, c_uint, c_longlong, c_longlong)`、`CallWindowProcW = (c_longlong, c_longlong, c_uint, c_longlong, c_longlong)`
- **涉及文件**：[desktop_main.py](file:///c:/Users/admin/.qclaw/workspace/desktop_main.py)

### 工作流删除/复制按钮失效
- **根因**：`wfDelete()`/`wfCopy()` 用 `document.querySelector(".wf-parent.selected")` 获取选中工作流，但工作流列表的点击事件只维护了 `.expanded` 类（展开/折叠），从未添加过 `.selected` 类。选择器永远返回 `null`，两个函数都直接 `return`。
- **解决方案**：`.selected` → `.expanded`
- **涉及文件**：[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### 子线程导入 web_app 导致 signal 注册报错
- **根因**：`desktop_main.py` 删除了 `import web_app` 后，`_start_flask` 线程中 `from web_app import app` 触发 `web_app.py` 模块级 `signal.signal()` 调用。Python 3.13 禁止在非主线程注册信号处理器，抛出 `ValueError: signal only works in main thread`。
- **解决方案**：`web_app.py` 中 `signal.signal()` 外包 `if threading.current_thread() is threading.main_thread():` 判断
- **涉及文件**：[web_app.py](file:///c:/Users/admin/.qclaw/workspace/web_app.py)

### 弃用 GitHub 远程推送，改为纯本地版本管理
- **决策**：2026-05-21 因国内访问 GitHub 网络不稳定（push 经常静默失败或超时），决定停止远程推送，使用纯本地 Git 管理版本。
- **改动**：更新 `github-push` skill 为只做本地 `git add` + `git commit --no-verify`，去掉所有推送相关步骤。remote origin 保留但不再使用。
- **涉及文件**：[.trae/skills/github-push/SKILL.md](file:///c:/Users/admin/.qclaw/workspace/.trae/skills/github-push/SKILL.md)
- **本地常用命令**：`git log --oneline` 查看历史，`git reset --soft HEAD~1` 撤销提交

### SortableJS CDN 脚本阻塞首次渲染导致白屏
- **场景**：2026-05-21 桌面版启动后页面 200 OK 但窗口空白，日志有两次 `GET /` 请求（间隔 2s 重试），[子类化] 信息正常打出，但页面始终不渲染
- **根因**：Sortable.js CDN 脚本（`<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js">`）放在 `<head>` 中是 **render-blocking** 的——浏览器遇到 `<script>` 暂停 DOM 构建，等 CDN 下载并执行完脚本后才继续解析 HTML。当 CDN 网络慢或不可达时，页面长时间白屏。2 秒后 WebView2 自动重试 `GET /` 也无济于事，因为每次都重新走 render-blocking 流程
- **解决方案**：将 `<script>` 从 `<head>` 移到 `</body>` 之前。MDN 官方文档确认这是标准做法："To avoid running a script before the DOM...simply place the script at the end of the document body, immediately before the closing `</body>` tag"。SortableJS 官方指南也推荐此做法。`buildWorkflowTab()` 是用户点击工作流页签时才调用，此时脚本早已加载完毕，不影响功能
- **涉及文件**：[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### flake8 清理经验
- **安全清理顺序**：① F401/F541/F841/F824（删除未用代码）→ ② E302/E305/E306/E127/E128（空行/缩进）→ ③ E722（bare except）→ ④ C901（圈复杂度）
- **autopep8 工具**：`autopep8 --in-place --select E302,E305,E306,E127,E128 <file>` 可批量自动修复空行/缩进问题，比手动改快得多。首批清理约 90 处问题仅需 3 条命令。
- **Round 1 效果**：4 个文件从 ~165 问题降至 ~122（消除 43 个 F401/F541/F841/E702/E231）
- **Round 2 效果**：E302/E305/E306/E127/E128 全部清除（消除 ~90 个）
- **涉及文件**：`desktop_main.py`、`toolbox_tab_upload.py`、`toolbox_tab_workflow.py`、`web_app.py`

### 翻译输出文件被占用的友好提示
- **场景**：翻译完成后 `wb.save(out_path)` 时，若输出文件已被 Excel 打开，抛出 `PermissionError [Errno 13]`，原始代码走 `except Exception` 打印完整 traceback。用户看到"翻译过程出错"后无法判断原因。
- **解决方案**：在 `except Exception` 之前添加 `except PermissionError` 分支，输出友好提示"输出文件被占用，请关闭 Excel 中已打开的文件后重试"
- **涉及文件**：[web_app.py](file:///c:/Users/admin/.qclaw/workspace/web_app.py)

### flake8 全面清零（~165→0）
- **场景**：2026-05-21 对 `desktop_main.py`、`toolbox_tab_upload.py`、`toolbox_tab_workflow.py`、`web_app.py` 四个文件做 flake8 全面清理，从约 165 个问题降至 0。
- **清理顺序**：
  1. **F401/F541/F841/F824/E702/E231**（删除未用代码/格式）：消除 43 个
  2. **E302/E305/E306/E127/E128**（空行/缩进）：消除 90 个，用 `autopep8 --select` 批量一键修复
  3. **E401/E402/E701/F541**（导入格式/多语句/无变量 f-string）：消除 13 个
  4. **E722 bare except**（裸 `except:` → `except Exception:`）：消除 20 个，用 Python 脚本批量正则替换
  5. **C901 圈复杂度**：消除 14 个（重构 7 个函数，剩余 7 个加 `# noqa: C901` 跳过）
  6. **W391**（文件末尾空行）：消除 2 个
- **关键经验**：
  - `autopep8` 只支持 E30/E12/E10 等格式类修复，不支持 E722（bare except）和 C901（圈复杂度）
  - E722 批量替换：用 Python `re.sub(r'^(\s*)except:\s', r'\1except Exception: ', content, flags=re.MULTILINE)` 安全替换所有裸 except
  - **C901 拆分模式**：提取嵌套 `def _run()` 为模块级函数，通过 args 参数传递闭包变量
- **涉及文件**：`desktop_main.py`、`toolbox_tab_upload.py`、`toolbox_tab_workflow.py`、`web_app.py`

### _cmp_worker.py 被 flake8 清理误删
- **场景**：2026-05-21 执行 SVN 对比时所有子进程报错 `exit=2`，提示 `can't open file '_cmp_worker.py'`。该文件被 Round 1 的 F841（删除未使用变量）清理中误删，但实际 `svn_oneclick_compare.py` 将其作为子进程通过 `sys.executable` 启动，属于跨进程调用而非模块导入，flake8 无法识别为"已使用"。
- **根因**：`_cmp_worker.py` 被 `svn_oneclick_compare.py` 通过 `subprocess.Popen([sys.executable, worker_script, ...])` 方式调用，不是 `import` 或 `from` 导入。flake8 静态分析只看 Python 级导入（`import X` / `from X import Y`），无法检测到字符串形式的子进程脚本路径，F841/F401 规则将其视为"未使用的文件"误删。
- **教训**：flake8 清理（特别是 F401/F841）**不可自动删除文件**，只能清代码引用。跨进程调用的脚本文件（`_cmp_worker.py`、`_github_push.py` 等）必须手动确认是否被 `subprocess`/`os.system`/`Popen` 等 API 使用。
- **恢复方法**：`git checkout <删除前一个提交>^ -- _cmp_worker.py` 从 git 历史恢复文件
- **涉及文件**：[_cmp_worker.py](file:///c:/Users/admin/.qclaw/workspace/_cmp_worker.py)

### SSE 实时日志流修复（并行工作流阻塞/日志不刷新）
- **场景**：2026-05-21 并行运行 2 个工作流时日志不实时刷新，且实际为串行执行。日志显示正常但第二个工作流等第一个跑完才开始。
- **根因**：`desktop_main.py` 使用 `werkzeug.serving.make_server("127.0.0.1", 18123, app)` 启动 Flask，默认单线程——SSE 长连接占用线程后，后续 HTTP 请求全部排队等待。`app.run(threaded=True)` 无效因为桌面版不经过 `if __name__` 路径。
- **解决方案**：
  1. `make_server(..., app, threaded=True)` 开启多线程，每个请求独立线程处理，SSE 不再阻塞其他请求
  2. `api_log_stream` 用 `stream_with_context` 包装生成器，确保每个 `yield` 立即推送到客户端
  3. Cache-Control 强化为 `no-store, must-revalidate` 禁止任何缓存
  4. 前端每个工作流日志用独立 DOM 节点（唯一 `bodyId`），不再是所有工作流共用一个 `wf_log_single`
  5. 播放按钮点击时 `appendChild` 而不是 `innerHTML=""`，避免清空已有日志
- **关键经验**：
  - `direct_passthrough=True` 要求 yield bytes，SSE 返回 str 会报错，不能加
  - 桌面版通过 `desktop_main.py` 的 `make_server` 启动，不是 `app.run()`，线程配置必须在 `make_server` 加
  - 多个并行 SSE 流需要独立的 DOM 容器 + 独立 EventSource 实例
- **涉及文件**：[desktop_main.py](file:///c:/Users/admin/.qclaw/workspace/desktop_main.py)、[web_app.py](file:///c:/Users/admin/.qclaw/workspace/web_app.py)、[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### lesson-log 与 github-push 合并为 record-and-commit
- **场景**：2026-05-21 用户要求将两个技能合并为一个。原先 `lesson-log`（记经验到知识库）和 `github-push`（本地 git 提交）被设计为独立的技能，但使用场景高度重合——解决一个复杂问题后通常需要两步一起做。每次分开调用增加沟通成本。
- **合并方案**：新技能 `record-and-commit` 将两个流程合并为流水线：Step 1-3 记录知识库 → Step 4 git 提交。用户说"记下来"或"提交"时自动识别要执行哪些步骤。旧目录 `.trae/skills/lesson-log/` 和 `.trae/skills/github-push/` 已删除。
- **涉及文件**：[record-and-commit/SKILL.md](file:///c:/Users/admin/.qclaw/workspace/.trae/skills/record-and-commit/SKILL.md)

### SVN update 提前到复制前 + 中文编码修复
- **场景**：2026-05-21 上传SVN功能运行时先复制文件再更新，导致新复制的文件可能被远程无冲突覆盖；同时 `svn update` 输出包含中文乱码。
- **解决方案**：
  1. `svn update` 提前到文件复制前执行（`_svn_update_first`），确保工作副本最新后再复制
  2. 新增 `_decode_svn_output` 函数：先尝试 UTF-8 解码，失败则用 GBK 解码（中文版 SVN 输出 GBK 编码）
- **关键经验**：SVN 中文版输出编码为 GBK（cp936），不能预设 UTF-8，需要双编码容错
- **涉及文件**：[web_app.py](file:///c:/Users/admin/.qclaw/workspace/web_app.py)

### 工作流步骤自动根据配置内容识别名称
- **场景**：2026-05-21 用户反馈工作流子步骤名称无法修改，要求改用规则自动生成。
- **规则**：
  - 打开表格 → 显示文件路径的文件名（`os.path.basename`）
  - 锁定SVN → 显示目标路径的文件名
  - 导出文字表 → 显示主文件路径的文件名
  - 上传SVN → 显示源目录的文件名，多个逗号分隔
  - 合并翻译 → 显示原始文件路径的文件名
  - 导出错误码 → 显示语言代码，多个逗号分隔
  - 合并表格 → 显示输入文件路径的文件名，多个逗号分隔
- **实现**：桌面GUI 用 `_wf_auto_name` 静态方法 + `_wf_save_config` 命名的 `_wf_edit_ctx` 自动触发；Web UI 用 `_wfAutoName` 在模态框保存时执行
- **涉及文件**：[toolbox_tab_workflow.py](file:///c:/Users/admin/.qclaw/workspace/toolbox_tab_workflow.py)、[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### 工作流复制/删除按钮移到父工作流 header
- **场景**：2026-05-21 用户觉得底部工具栏的复制和删除按钮操作路径太长，要求放到每个父工作流自己的 header 上
- **解决方案**：底部工具栏只保留"新建"；每个父 header 的 ▶ 播放按钮右边加 📋 复制按钮（直接复制）、右上角加 ✕ 删除按钮（弹窗确认）
- **涉及文件**：[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)
- **全对判断**：`!q.answered || answerSelectedIndex===undefined` 任一未答即不算全对
- **脚本位置**：`自动学习/auto_exam.js`

### 学习脚本 (`自动学习/auto_learn_pip_loop.js`)
去掉了画中画并行播放，改为纯顺序播放。核心逻辑：
```
while (true):
  todo = getUncompleted()
  取 todo[0] → 点击 → mute → 等 isComplete
  防死循环: 连续3轮无进展退出
  无视频: 主动标记 selectedLesson.isComplete = true
```
- 脚本位置：`自动学习/auto_learn_pip_loop.js`
- 入口：课程列表页 Console 粘贴，点击按钮启动

### 通用教训
- **不要相信 Vue data/methods**，用 DOM 操作模拟真实用户行为
- **两阶段比混合循环稳定**：先全部空提交，再统一处理查看→重做
- **每次修改后必须 graphify update**

## 2026-05-21 二次确认弹窗 UI 统一

### 背景
策划工具箱桌面版（Web UI）有三处使用原生 `confirm()` / `alert()` 弹窗（刷新文件错误提示、删除工作流、删除步骤），风格粗糙、位置僵硬，与深色后台 UI 不统一。

### 解决方案
1. **CSS 层**：新增 `.confirm-overlay`（全屏遮罩 flex 居中）、`.confirm-dialog`（圆角深色卡片）、`.confirm-dialog-title/msg/actions`、`.btn-danger`（删除操作红色按钮）
2. **HTML 层**：在 `.app` 容器外新增确认弹窗 DOM 结构，`z-index:2000` 高于所有页面元素
3. **JS 层**：
   - `showConfirm(options)` — Promise 化 API，支持 `title`/`message`/`confirmText`/`cancelText`/`danger` 参数
   - `showAlert(message, title)` — 仅确定按钮的提示弹窗，通过 `cancelText:""` 隐藏取消按钮
   - 弹窗居中原理：overlay 用 `position:fixed; inset:0; display:flex; align-items:center; justify-content:center` 实现应用窗口正中央定位
4. **替换**：3 处原生调用全部替换为 `await showConfirm()` / `await showAlert()`

### 涉及文件
[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### 设计要点
- 使用 UI 系统已有色彩 Token：`--bg2`（弹窗背景）、`--line`（边框）、`--sub`（消息文字）、`--text`（标题文字）
- 删除操作确认按钮使用 `.btn-danger`（`--danger:#ff637d` 渐变），与常规 `.btn-primary`（蓝色）区分危险操作
- 弹窗宽 400px，使用 8px 网格间距（gap:8px, padding:24px, margin:12/20px）
- 点击遮罩层空白区域可关闭弹窗（返回 false）

## 2026-05-21 工作流列表 UI 多项优化

### 变更清单
1. **删除按钮移到右上角** — 父工作流和子工作流的 ✕ 删除按钮均改为 `position:absolute; top:0; right:0`，移出 inline 布局，无背景无边框，hover 变红色
2. **复制按钮样式统一** — 从透明无背景改为与播放按钮一致的蓝色半透明背景 + hover 放大效果；📋 emoji 替换为 14×14 SVG 线框复制图标
3. **步骤数显示** — 从带背景的 badge 改为纯暗色文字紧跟在名称后（`名称  2步骤`），不抢眼
4. **名称可编辑** — 名称后加极淡 ✎ SVG 图标（opacity 0.25→hover 0.6），点击名称/步骤/图标整块进入内联输入，Enter/失焦保存，Esc 取消
5. **点击区域分离** — `.wf-parent-name` 去掉 `flex:1` 不再撑满，空白区域点击触发展开/折叠

### 涉及文件
[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)

### 设计要点
- `.wf-del-btn` / `.wf-child-del-btn` — 22×22 透明按钮，右上角 `top:0;right:0`，字体 11px，无背景无边框
- `.wf-copy-btn` — 与 `.wf-play-btn` 完全相同的样式（蓝底蓝字），hover 变白放大
- `.wf-parent-name` — `white-space:nowrap` 防止换行，点击内联编辑替换为 `<input class="wf-name-input">`
- 所有的 `.textContent` 读取都改为从 `config.workflows[wfIdx].name` 获取，避免名称 span 内 SVG/步骤数文字干扰

## 2026-05-12 DeepSeek API 缓存命中优化

### 背景
翻译功能每次调用 DeepSeek API 时都把提示词 + 参考 + 待翻译文本 + 格式指令全部拼入 `system` 消息，
导致 system prompt 每次请求都不同，缓存命中率接近 0%。

### 修复
- `system` → 只放固定的 prompt template（角色定义 + 任务描述），跨批次不变
- `user` → 放所有动态内容：参考、格式指令、待翻译文本
- 从 API 响应 `usage` 提取 `prompt_cache_hit_tokens` 并打印命中率

### 价格参考（V4-Flash）
| 场景 | 价格 |
|---|---|
| 输入缓存命中 | 0.02元/百万tokens |
| 输入缓存未命中 | 1元/百万tokens |
| 输出 | 2元/百万tokens |

### 文件
- 规则：`AGENTS.md` → 「DeepSeek API 缓存优化规则」
- 代码：`toolbox_tab_translate.py` → `_call_api_multitarget()`

## 2026-05-14 本地 Excel 文件快速对比方案

### 背景
需要快速对比两个本地 .xlsm 文件（Texts1.xlsm / Texts2.xlsm，各 6.6MB / 58 sheets / 约12万行）。

### 尝试过的方案

1. **`svn_oneclick_compare.py` 的 `_parse_excel_lxml`**（iterparse）
   - 全量解析 58 sheet / 12万行 → 单文件 ~13s，pickle 26MB
   - 第二个文件解析时 Python 进程被系统杀死（OOM），无法完成对比
   - **不适合双文件全量解析**

2. **先 ZIP 级 hash 找差异 sheet → 只解析差异 sheet**
   - ✅ **最终方案**，9.89s 完成
   - 25 个 sheet XML 不同（24 个同 size→仅格式差异，1 个 size 不同→实质内容差异）
   - 只解析一个 sheet27，发现 4 处差异

### 对比结果
| 行 | 列 | Texts1 | Texts2 |
|---|---|---|---|
| 8476 | B | `{2}血量` | `{2}%血量` |
| 8477 | B | `{1}理智值` | `{1}%理智值` |
| 8499 | B | `退回到了{1}` | `退回到了噬魂深渊场景` |
| 8566 | - | 存在 | 删除 |

### 工具位置
- **`quick_excel_diff.py`**：对两个 .xlsm/.xlsx 文件快速 diff
  - 用法：修改脚本顶部 `f1`/`f2` 路径后运行
  - 策略：ZIP hash 差异检测 → 只解析 size 不同的 sheet 单元格 → 输出差异报告
  - 输出：`_cmp_result.txt`

### 教训
- `_parse_excel_lxml` 虽快但全量解析 6MB+/12万行 会导致 OOM，双文件无法在同一个进程完成

### 语义合并版本计数不刷新的 bug
- **场景**：2026-05-22 语义合并页签全选→清空/反选后，底部已选版本数不刷新，始终显示全选时的数字
- **根因**：`_updateMergeVersionCount()` 用 `Object.keys(_mergeData.checkedRevs).length` 计数，但清除操作只把值设为 `false`，key 仍然存在于对象中，导致 `Object.keys` 始终返回全选时的数量
- **解决方案**：改为 `Object.values(_mergeData.checkedRevs).filter(Boolean).length`，只统计值为 `true` 的 key 数量
- **涉及文件**：[templates/index.html](file:///c:/Users/admin/.qclaw/workspace/templates/index.html)
- 双文件对比的正确策略：先轻量级探测（ZIP hash）→ 只对差异 sheet 做重解析
- 同 size 不同 hash 的 sheet 是格式/样式/压缩差异，不影响单元格数据
