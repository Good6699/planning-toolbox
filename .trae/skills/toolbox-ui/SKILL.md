---
name: "toolbox-ui"
description: "策划工具箱 UI 开发规范与设计系统。Invoke when modifying templates/index.html CSS/HTML/JS, adjusting visual layout, or any UI work on 策划工具箱 project."
---

# 策划工具箱 UI 开发助手

## 项目概要

- **主 UI 文件**: `templates/index.html`（单文件 SPA：CSS + HTML + JS 一体）
- **后端**: `web_app.py`（Flask，路由 `/api/*`，SSE 日志流）
- **启动器**: `web_launcher.py`（Flask 直接运行，端口 18123）
- **桌面入口**: `策划工具箱GUI.vbs`（VBScript 自动找 Python 并启动）

## UI 设计系统（不得违反）

### 色彩 Token

```css
--bg:#0f1115;     /* 最深底 */
--bg2:#151821;
--panel:#171b24;
--panel2:#1d2330;
--text:#f2f5ff;    /* 主文字 */
--sub:#aeb8cc;     /* 次级文字 */
--dim:#7f8aa3;     /* 最淡文字 */
--accent:#5ea2ff;  /* 主强调蓝 */
--success:#52d273;
--danger:#ff637d;
```

### 字体体系

- **字体栈**: `"Segoe UI","Microsoft YaHei UI","PingFang SC",sans-serif`（系统字体，不加载 Google Fonts）
- **根字号**: `font-size: 15px`（深色后台桌面工具基线，适配 1920×1080 设计基准）
- **布局单位**: 全部用 `px`（桌面工具不需要 rem 响应式，使用 px 精确控制）
- **body font-weight**: `500`
- **抗锯齿**: `-webkit-font-smoothing: auto`
- **断点**: CSS 断点只处理布局，不改 font-size

### 尺寸规范（基准 15px 根，深色后台工具）

| 元素 | 高度 | 字号 | 圆角 |
|------|------|------|------|
| `.topbar` | `68px` | - | - |
| `.nav-btn` | `36px` | `12px` | `8px` |
| `.btn` | `var(--btn-h)` (36px) | `13px` | `8px` |
| `.btn-sm` | `32px` | `12px` | `8px` |
| `.action-center .btn` | `var(--btn-h-lg)` (42px) | `14px` | `12px` |
| `input, select` | `36px` | `13px` | `8px` |
| `textarea` | `min-height: 80px` | `13px` | `8px` |
| `.page-title h2` | - | `20px` | - |
| `.card` | `padding: 16px` | - | `16px` |
| `.content` | `padding: 20px` | - | - |
| `.log` | `height: 320px` (固定) | `12px` | `8px` |

### 间距规约

```css
--space-xs:4px;  --space-sm:8px;
--space-md:12px;  --space-lg:16px;
--space-xl:20px;  --space-2xl:24px;  --space-3xl:32px;
--btn-h:36px;  --btn-h-lg:42px;
```

所有 padding / margin / gap / 控件高度只能从这套 8px 网格取值（4/8/12/16/20/24/32/40/48）。不要出现 14/18/22/29/37 等魔数。
所有布局 grid gap 统一 `16px`，卡片间距仅靠 gap。不要再有 inline `style="height:2.25rem;font-size:0.8125rem;margin-bottom:1rem;padding:3.75rem"`——用 `.btn-sm`、`.card-header.compact`、`.empty-state` 等 class。

### 布局规约

- **sidebar**: `260px`（小屏 `1000px` 断点折叠为 `72px` 仅显示图标），左侧固定，`backdrop-filter: blur(24px)`
- **workbench**: `grid-template-columns: repeat(auto-fit, minmax(360px, 1fr))` — 自动响应：大屏双列、中屏单列
- **wf-layout**: `grid-template-columns: 320px minmax(0,1fr)` — 左列表 + 右详情，非 auto-fit
- **translate-layout**: `grid-template-columns: repeat(auto-fit, minmax(420px, 1fr))`
- **svn-layout**: `grid-template-columns: minmax(0,1fr) 580px`（SVN 专用），日志跨列全宽 `grid-column:1/-1`，`1100px` 断点单列
- **upload-layout**: `grid-template-columns: minmax(0,1fr) 580px`，同 svn-layout 模式
- **tr-layout**: `grid-template-columns: minmax(0,1fr) 580px`（翻译专用），`tr-log-wrap` 全宽
- **所有布局 grid gap**: `16px`（统一值）
- **body**: `overflow: auto; min-height: 100%`
- **.content**: `flex:1; overflow:auto; padding:20px; width:100%; min-width:0`
- **.content-inner**: `width:100%; max-width:1800px; margin:0 auto` — 居中包装
- **.action-center**: `margin: 20px 0 8px`
- **.action-center .btn**: `min-width:260px; height:var(--btn-h-lg); border-radius:12px; font-size:14px`
- **.card**: `padding: 16px; border-radius: 16px; margin-bottom: 0`
- **.card-header**: `display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px; min-height:32px`
- **.card-header.compact**: `margin-bottom: 8px`（日志区标题用 compact）
- **.card-title**: `margin-bottom: 10px`
- **.form-group**: `margin-bottom: 12px`
- **.form-group label**: `margin-bottom: 4px`
- **.log**: `height: 320px; min-height: 320px; max-height: 320px` — 所有页面统一固定高度
- **.btn-sm**: `height: 32px; font-size: 12px` — 日志清空等小按钮
- **.empty-state**: `padding: 48px 24px; color: var(--sub); text-align: center` — 空状态占位
- **.flex-row**: `display:flex; gap:10px; flex-wrap:wrap`
- **.btn-primary**: `box-shadow: 0 12px 32px rgba(74,141,255,.32), inset 0 1px 0 rgba(255,255,255,.24)`
- **响应式断点**: `1200px` 所有 Grid 变单栏，`1000px` sidebar 折叠至 `72px`（隐藏标题和 logo 文字），`900px` sidebar 变水平全宽

### 禁止事项（历史踩坑记录）

1. **禁止 `html { font-size: clamp(...vw...) }` 流体根字体** — 屏幕越大所有 rem 疯狂变大，sidebar 失控
2. **禁止 24px 大字号根字体** — 桌面工具不需要大字号，应使用紧凑 14px + px 精确控制
3. **禁止 `-webkit-font-smoothing: antialiased`** — Windows Chromium 下文字发虚
4. **禁止 Google Fonts 加载** — 用系统字体栈，不依赖外部网络
5. **禁止 `flex-shrink:0` 搭配固定宽度** — 会导致内容溢出容器
6. **禁止 CSS `zoom` 属性** — 会导致浏览器缩放错乱、布局计算异常、字体模糊、Chrome DPI 计算异常
7. **禁止 `minmax(大px值, Nfr)` 锁死最小宽度** — 如 `minmax(760px,1.3fr)` 会导致窗口无法缩小，改用 `repeat(auto-fit,minmax(420px,1fr))`
8. **禁止 `.content` 设 `max-width`** — 通过 `.content-inner` 层做居中包装，`.content` 本身只负责 padding 和 overflow
9. **禁止 `overflow: hidden` 在 `html,body`** — 页面必须可滚动，用 `overflow: auto; min-height: 100%`
10. **禁止 card 同时用 grid gap 和 margin-bottom** — 只用 grid gap 统一控制间距
11. **禁止 8px 网格外的魔数尺寸** — 所有值只能是 4/8/12/16/20/24/32/40/48，不要出现 14/18/22/29/37
12. **禁止 inline style 硬编码间距和高度** — 用 `.btn-sm` `.card-header` `.empty-state` 等 class，不写 `style="height:2.25rem;margin-bottom:1rem"`

## JavaScript 架构

### 全局对象
```javascript
const S = {};  // 每个 tab 的状态容器：S.svn, S.upload, S.workflow, S.translate
```

### 导航系统
```javascript
const nav = [
  {key:"svn", label:"SVN 记录"},
  {key:"upload", label:"上传 SVN"},
  {key:"workflow", label:"工作流"},
  {key:"translate", label:"翻译"},
];
```

### 事件委托（不要用内联 onclick）
```javascript
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  // dispatch to appropriate handler
});
```

### Tab 渲染
- `buildTab(key)` 首次访问时渲染 HTML 到 `S[key].panel`
- `switchTab(key)` 切换 active 状态
- 每个 build*Tab 函数负责自己的 DOM 绑定
- SSE 日志通过 `S[key].logEl` 引用

### 配置 API
- `GET /api/config` → `loadConfig()`
- `POST /api/config` → `saveConfig(updates)`
- 任务执行: `POST /api/svn/run` 等，返回 `{task_id}`，SSE 流式读取 `/api/task/{id}/stream`

### 目录拖放
- `enablePathDrop(inputId, callback)` — 通用目录拖入函数，注册到 DOMContentLoaded
- 支持的输入框: `svn_output`, `upload_src`, `upload_tgt`, `tr_src`, `tr_ref`, `tr_out`
- 拖入时高亮边框（`--accent` 色）+ 背景（`#131c28`），松开自动填入路径

## 修改 UI 的流程

1. 不要动 JS 逻辑，除非明确需要
2. 只改 `<style>` 块内的 CSS
3. 修改后检查:
   - 所有尺寸属于 8px 网格（4/8/12/16/20/24/32/40/48）
   - 无 inline `style="height:2.25rem;font-size:0.8125rem;margin-bottom:1rem;padding:3.75rem"`
   - 布局用 `repeat(auto-fit,minmax(360px,1fr))`（workbench），wf-layout 用 `320px minmax(0,1fr)`
   - `.content` 没有 `max-width`，`.content-inner` 有 `max-width:1800px` 居中
   - `.card` 无 `margin-bottom`，间距仅靠 grid gap `16px`
   - `.card-header` / `.card-header.compact` 统一样式
   - `.btn-sm` / `.empty-state` 等 CSS class 替代 inline style
   - `.action-center .btn` = `260px × var(--btn-h-lg)` (42px)，`margin: 20px 0 8px`
   - `.log` = `height: 320px` 固定
   - `* { box-sizing: border-box }` 必须存在
   - 没有 CSS zoom 属性
4. 改完刷新浏览器 `http://127.0.0.1:18123` 验证
