# Tasks: SVN 输入框 UX 增强

- [x] Task 1: 后端新增 `/api/svn/detect` 路由
  - [x] 1.1 接收 `{path}`，执行 `svn info --show-item url <path>`，返回 `{ok:true, url:"..."}` 或 `{ok:false, error:"..."}`
  - [x] 1.2 处理 svn 命令不可用、路径不存在、非 SVN 目录等异常
  - [x] 1.3 位置：`web_app.py`，与现有 `/api/open/folder` 相邻

- [x] Task 2: 前端 `svn_url` 输入框改造（拖拽 + 打开按钮 + 自动保存）
  - [x] 2.1 在 `buildSvnTab()` 的 `svn_url` 卡片中，在输入框右侧新增 "打开" 按钮（`data-action="open-svn-url"`）
  - [x] 2.2 在 `DOMContentLoaded` 中注册 `enablePathDrop("svn_url", onSvnUrlDrop)`
  - [x] 2.3 实现 `onSvnUrlDrop(path)` 回调：调用 `/api/svn/detect` → 成功填 URL 并自动保存 → 失败 toast 提示
  - [x] 2.4 事件委托中新增 `open-svn-url` case：判断路径有效性后调用 `/api/open/folder`
  - [x] 2.5 在 `buildSvnTab()` 中给 `svn_url` 和 `svn_output` 添加 `blur` 事件自动保存

- [x] Task 3: CSS 日期选择器图标提亮
  - [x] 3.1 在 `<style>` 块中新增 `input[type="date"]::-webkit-calendar-picker-indicator` 样式（`filter: invert(1)`）
  - [x] 3.2 确保不影响其他页面（仅在 dark 主题下生效，已是全局 dark）

# Task Dependencies
- Task 2.3 依赖 Task 1（需要 `/api/svn/detect` 先就绪）
- Task 2 其他子任务与 Task 1 可并行
- Task 3 独立，可与 Task 1/2 并行
