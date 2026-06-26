# 实施清单

## 后端
- [ ] 1.1 添加 `/api/prefab/scan` 路由（扫描路径，返回 .prefab 列表）
- [ ] 1.2 添加 `/api/prefab/clear-text` 路由（启动清理线程，返回 task_id）
- [ ] 1.3 添加 `_exec_prefab_clear_text()` 函数（正则替换逻辑）

## 前端
- [ ] 2.1 nav 数组追加 `{key:"prefab", label:"修改预制"}`
- [ ] 2.2 tabMeta 追加 prefab 条目
- [ ] 2.3 buildTab switch 追加 prefab case
- [ ] 2.4 新增 `buildPrefabTab()` 函数（模式选择 + 拖拽区 + 日志区 HTML）

## 前端 — 拖拽交互
- [ ] 3.1 拖拽区 dragover/dragleave CSS 反馈
- [ ] 3.2 drop 事件 → 扫描 → 清理 → SSE 日志闭环
- [ ] 3.3 文件摘要动态更新

## 验证
- [ ] 4.1 拖入单个 .prefab → 自动清理 → 日志正确
- [ ] 4.2 拖入文件夹 → 展开所有 .prefab → 逐个清理
- [ ] 4.3 拖入多个文件 + 文件夹混合 → 正确处理
- [ ] 4.4 拖入非 .prefab 文件 → 跳过并显示日志
- [ ] 4.5 清理后 m_Text 确实为空，其他内容不变
