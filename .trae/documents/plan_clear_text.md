# 修改预制 - 一键清理文字 Pagesgn

## 目标
在策划工具箱新增"修改预制"页签，提供模式选择功能，首个模式为"一键清理文字"——用户将 .prefab 文件拖入后自动将所有组件中的 `m_Text:` 值清空。

## 变更清单

### 1. `templates/index.html`

#### 1.1 注册页签
- `nav` 数组追加 `{key:"prefab", label:"修改预制"}`
- `buildTab()` switch 追加 `case "prefab": buildPrefabTab(panel); break;`

#### 1.2 新增 `buildPrefabTab(panel)` 函数
- HTML 结构：
  - 模式选择下拉框（`<select>`），目前只有"一键清理文字"
  - 拖拽区（接受文件/文件夹拖放）
  - 已拖入文件摘要（文件数、.prefab 数）
  - 日志面板（复用 `.log` 样式）

#### 1.3 拖拽处理逻辑
- 监听拖拽区 `dragover` / `drop` 事件
- `drop` 触发时：
  - 读取拖入的路径列表
  - 将文件传给后端 `/api/prefab/scan` 扫描（文件夹展开为 .prefab 列表）
  - 后端返回文件列表后自动调用 `/api/prefab/clear-text` 执行清理
- 日志通过 SSE `/api/log/stream/<task_id>` 流式输出

### 2. `web_app.py`

#### 2.1 新增 `/api/prefab/scan` POST
- 输入：`{paths: ["/path/to/file.prefab", "/path/to/dir"]}`
- 输出：`{files: ["/path/to/a.prefab", ...], count: N}`
- 对每个路径：文件直接加，目录递归扫描 `**/*.prefab`

#### 2.2 新增 `/api/prefab/clear-text` POST
- 输入：`{files: ["/path/to/a.prefab", ...]}`
- 处理流程：
  1. 为每个文件生成一个 task_id
  2. 启动后台线程执行
  3. 返回 task_id，前端 SSE 订阅日志

#### 2.3 清理逻辑 `_exec_clear_text(file_path, q)`
1. 读文件为文本
2. 正则匹配 `m_Text:` 行（匹配缩进 + `m_Text:` + 任意值）
   - 模式：`^( +m_Text:).*$` → 替换为 `\1`
   - 多行匹配（`re.MULTILINE`）
3. 统计替换次数
4. 有改动则写回文件
5. 每替换一行输出一条节点级日志

#### 2.4 日志示例
```
[扫描] D3.prefab — 找到 3 个 m_Text 节点
[清理] D3.prefab L42: m_Text "确认" → 已清除
[清理] D3.prefab L55: m_Text "取消" → 已清除
[清理] D3.prefab L78: m_Text "提示信息" → 已清除
[DONE] 共处理 5 个文件，清理 12 处文本，跳过 0 个非 .prefab 文件
```

## 注意事项
- `m_Text:` 行在 Unity YAML 中缩进为 2 个空格
- 空 `m_Text:`（无值）不做替换，不算"清理"
- 非 .prefab 文件跳过并日志提示
- 正则尽量精确，避免误改注释行或其他同名属性
