- **2026-04-16**：记忆系统启用

## 技术规范偏好

- Windows批处理脚本开发中：使用UTF-8 with BOM格式解决中文乱码；注意enabledelayedexpansion与特殊字符(!)的冲突；set /p读取输入需处理引号；endlocal & set在for循环内会导致变量重置
- **批处理输入处理最佳实践**：用户输入可能包含引号，必须用 `for /f "delims=" %%a in ("!VAR!") do set VAR=%%~a` 去除；使用 `setlocal EnableDelayedExpansion` + `!VAR!` 语法避免特殊字符（& | < > ^）导致解析错误
- **批处理调试技巧**：闪退问题用`setlocal EnableDelayedExpansion`+分步echo定位；输入问题检查是否带引号；编码问题用Python生成`utf-8-sig`格式文件
- SVN工具开发偏好：Python脚本配合.bat启动器；使用PowerShell替代%date%获取日期以避免中文Windows系统格式问题；revision参数避免使用大括号{}以免被识别为日期格式
- Excel对比工作偏好：按行对比，关注ID和SC列的变化，操作类型区分为新增和修改
- 中文Windows批处理也可用纯GBK编码替代UTF-8（与代码页936一致），无需chcp 65001
- **2026-04-16**：记忆系统启用
- **2026-05-12**：Web版策划工具箱UI全面重构 + 后端工作流接入

## 当前项目与关注

- SVN版本对比工具（v9+）：多进程并行解析 + 下载/解析流水线 + ID Map缓存 + 预过滤；Python GUI (svn_compare_gui.py)
- SVN工具GUI已改为Python实现（svn_compare_gui.py），配置持久化到svn_gui_config.json
- **Web版策划工具箱**：Flask单文件SPA (`web_app.py` + `templates/index.html`)，端口18123

## Web版策划工具箱架构 (2026-05-12)

### 后端 (`web_app.py`)
- Flask直接运行，端口18123，SSE日志流 `/api/log/stream/<task_id>`
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

### 核心文件位置
- 启动：`web_launcher.py`
- 后端：`web_app.py`
- 前端：`templates/index.html`
- 配置：`svn_gui_config.json`
- 规范：`.trae/skills/toolbox-ui/SKILL.md`
- 知识图谱：`graphify-out/`（`graphify_quick.py --no-viz` 增量更新）

## 经验与决策

- svn cat 替代 svn export 可直接读入内存，提升SVN导出速度
- svn diff --summarize 可先判断版本间文件差异，避免对无变化文件做完整export
- **多进程解析Excel**：openpyxl read_only模式 + ProcessPoolExecutor 并行解析，比串行pandas快30倍
- **下载/解析流水线**：下载批次后立即提交解析任务，不等待全部下载完成，总时间=max(下载,解析)而非相加
- **ID Map缓存**：对比阶段预构建ID→SC映射并缓存，避免每次对比都重建，对比提速约50%
- **Windows批处理编码陷阱**：
  - `write` 工具默认写入UTF-8无BOM，中文Windows批处理必须用Python以`utf-8-sig`格式写入
  - 通过管道执行批处理时（如`echo input | script.bat`），反斜杠会被当作转义符，导致`\.q`被解析为命令
  - 用户输入常带引号（如`"2.txt"`而非`2.txt`），必须用`for /f`循环去除，简单的`%VAR:"=%`不够可靠
- svn info返回的URL是编码后的中文路径，需用urllib.parse.unquote解码
- Texts.xlsm 的 header 列名是 ::ID:: 和 ::SC::（带 :: 前后缀），列名匹配必须包含 ::ID:: 和 ::SC:: 才能正确识别
- **Windows文件名禁止冒号**：cache_key拼入 `::ID::` 等含冒号的列名后作为文件名，Windows拒绝创建（`OSError [Errno 22]`），必须用 `_safe_cache_key()` 替换非法字符。`except: pass` 吞掉此类异常会导致缓存永远为空且无报错。
- **多进程IPC开销**：worker返回parsed dict（18MB/个），32个pair需传1.15GB数据到主进程，严重影响性能。应让worker直接写磁盘缓存，只返回轻量结果（diff_rows + 元数据）。
- **`_cache_hits/_cache_misses` 计数器在worker进程递增但不回传主进程**，导致主进程的缓存统计永远为0不打印

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
- 双文件对比的正确策略：先轻量级探测（ZIP hash）→ 只对差异 sheet 做重解析
- 同 size 不同 hash 的 sheet 是格式/样式/压缩差异，不影响单元格数据
