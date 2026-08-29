# 实施任务

1. 新增 `toolbox_core/atlas_migration.py`：路径限制、prefab/meta 解析、计划、草稿、复制、最终解析、原子修改、TXT。
2. 新增 `toolbox_core/tests/test_atlas_migration.py`，覆盖解析、命名、计划、复制、恢复和写入。
3. 修改 `toolbox_core/web_app.py`，接入草稿、计划、复制、解析和修改 API/SSE 任务。
4. 修改 `toolbox_core/tab-prefab.js`，增加模式切换、三段布局、拖拽规划、预览编辑和阶段操作。
5. 修改 `toolbox_core/templates/index.html`，增加符合设计系统的图集迁移样式。
6. 修改 `toolbox_core/core.js`，登记 prefab 后台任务状态映射。
7. 运行 Python/JS 静态检查、自动化测试、graphify_quick 和 SVN 差异检查。
