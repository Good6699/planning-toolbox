# 实施任务

## Task 1: 后端 — 新增 /api/prefab/scan 和 /api/prefab/clear-text
- 文件: `web_app.py`
- 位置: 在已有 API 路由区域末尾添加
- 新增函数: `_exec_prefab_clear_text()`
- 新增路由:
  - `app.route("/api/prefab/scan", methods=["POST"])`
  - `app.route("/api/prefab/clear-text", methods=["POST"])`

## Task 2: 前端 — 注册"修改预制"页签
- 文件: `templates/index.html`
- nav 数组追加 `{key:"prefab", label:"修改预制"}`
- tabMeta 追加 `prefab:{title:"修改预制", sub:"预制文件批量修改工具"}`
- buildTab switch 追加 `case "prefab": break;`
- 新增 `buildPrefabTab(panel)` 函数

## Task 3: 前端 — 拖拽区和自动执行逻辑
- 文件: `templates/index.html` 内 `buildPrefabTab`
- 拖拽区 HTML + CSS
- 文件扫描 → 自动清理 → SSE 日志
