# 修改预制 — 一键清理文字 功能规格

## 概述
策划工具箱新增"修改预制"页签，以模式选择方式提供预制修改工具。首个模式"一键清理文字"将拖入的 .prefab 文件中所有 `m_Text:` 值清空。

## 前端（templates/index.html）

### 页签注册
```javascript
// nav 数组追加
{key:"prefab", label:"修改预制"}

// tabMeta 追加
prefab:{title:"修改预制",sub:"预制文件批量修改工具"}

// buildTab switch 追加
case "prefab": buildPrefabTab(panel); break;
```

### buildPrefabTab(panel) UI 结构
- **模式选择行**：`<select id="prefab_mode">`，选项 `"一键清理文字"`
- **拖拽区**：居中虚线框，带"拖拽文件/文件夹到此处"提示文字
- **文件摘要**：动态显示"已扫描 X 个 .prefab 文件"
- **日志面板**：带 `.log` 样式

### 拖拽逻辑
- 监听 `#prefab_dropzone` 的 `dragover` / `dragleave` / `drop`
- `drop` 时提取所有路径（文件夹展开为子路径）：
  1. POST `/api/prefab/scan` → 获取 .prefab 文件列表
  2. 摘要更新文件数
  3. 自动 POST `/api/prefab/clear-text` → 获取 task_id
  4. 通过 SSE `/api/log/stream/<task_id>` 流式输出日志
- 页签切换/重建时保留 `prefabDropZone` 挂载点

## 后端（web_app.py）

### /api/prefab/scan POST
```python
输入: {"paths": ["D:/a.prefab", "D:/folder"]}
输出: {"files": ["D:/a.prefab", "D:/b.prefab", ...], "count": 5}
```
- 文件直接加入
- 目录递归 `**/*.prefab`

### /api/prefab/clear-text POST
```python
输入: {"files": ["D:/a.prefab", ...]}
输出: {"task_id": "t_xxxx"}
```
- 创建 task_id、log 队列
- 启动 `_exec_prefab_clear_text(files, q, task_id)` 线程
- 返回 task_id

### _exec_prefab_clear_text(files, q, task_id)
```python
def _exec_prefab_clear_text(files, q, task_id):
    total_cleared = 0
    total_files = 0
    for fp in files:
        if not fp.lower().endswith(".prefab"):
            q.put(f"[跳过] {fp} — 不是 .prefab 文件")
            continue
        raw = open(fp, "r", encoding="utf-8").read()
        lines = raw.split("\n")
        new_lines = []
        cleared = 0
        for i, line in enumerate(lines):
            m = re.match(r"^( +)(m_Text:)(.*)$", line)
            if m and m.group(3).strip():
                new_lines.append(m.group(1) + m.group(2))
                cleared += 1
                q.put(f"[清理] {os.path.basename(fp)} L{i+1}: {m.group(3).strip()[:40]} → 已清除")
            else:
                new_lines.append(line)
        if cleared:
            open(fp, "w", encoding="utf-8").write("\n".join(new_lines))
            total_cleared += cleared
        total_files += 1
        q.put(f"[完成] {os.path.basename(fp)} — 清理 {cleared} 处 m_Text")
    q.put(f"[DONE] 共处理 {total_files} 个文件，清理 {total_cleared} 处文本")
    q.put(None)
    _log_queues.pop(task_id, None)
```

### 关键正则
```
^( +)(m_Text:)(.*)$
```
- `^( +)` — 行首缩进（Unity YAML 2空格）
- `(m_Text:)` — 字段名
- `(.*)$` — 值部分
- 仅当值非空时才替换（`m.group(3).strip()` 为真）
