---
name: "step-by-step"
description: "Breaks implementation tasks into ordered phases with exact file paths, change scope, and verification. Invoke when implementing multi-step feature or fixing a bug with clear before/after logic."
---

# Step-by-Step Implementation

将实现任务分解为严格有序的步骤，每个步骤包含精确的文件路径、变更范围和验证方法。

## 使用流程

### ⚠️ Phase 0 前必须执行：查阅图谱报告

在开始任何问题分析或变更定位之前，**必须先读 graphify 图谱报告**：

1. 使用 `Read` 工具打开 `graphify-out/GRAPH_REPORT.md`
2. 查阅 **核心模块、代码文件结构、社区分组** 三个章节，了解代码全局结构
3. 在**代码文件结构**中确认待修改文件的存在性和关联节点数
4. 在**社区分组**中找到待修改功能所属的社区，确认涉及的上下游文件
5. **不得跳过此步骤**，图谱能揭示 SearchCodebase 搜不到的跨文件关联关系

### Phase 0: 问题分析

回答三个问题：

| 问题 | 目的 |
|------|------|
| 当前行为是什么？ | 明确现状（客观，不掺杂判断） |
| 期望行为是什么？ | 明确目标（可测试的描述） |
| 差距在哪里？ | 找到需要改变的点 |

输出：一段清晰的"现状→目标"描述。

### Phase 1: 变更定位

列出所有需要修改的函数及其所在的精确文件路径和行号：

```
文件: path/to/file.py
函数/类: ClassName.method_name    行号: L42-L67
修改原因: 一段话说明
```

如果涉及新增函数，同样列出。

### Phase 2: 变更点详述

每个变更点必须包含：

```
变更点 N: [简短标题]
文件: [精确路径]
位置: [函数/行号]
之前: [3-10行代码片段，精确匹配]
之后: [3-10行代码片段]
依赖: [依赖的其他变更点编号，或"无"]
```

规则：
- "之前"和"之后"必须是在原文件中的 **contiguous code block**，可直接用于 `SearchReplace`
- 如果变更涉及多个分散位置，每个位置独立编号
- 依赖关系必须明确：如果变更点 B 需要变更点 A 先完成，B 依赖 A

### Phase 3: 实施顺序

按依赖拓扑排序：

```
Phase 0: 基础设施（如新增函数、全局变量）
Phase 1: 核心逻辑修改（按依赖顺序）
Phase N: 清理（删除死代码、重命名等）
```

### Phase 4: 逐项实施

按实施顺序逐一处理每个变更点。每个变更点完成后：
1. 验证语法：`python -m py_compile <file>`
2. 验证逻辑：确认变更后的代码符合预期

### 错误处理

如果某个变更点实施后发现新问题：
1. 回退该变更点
2. 回到 Phase 1，更新变更定位
3. 重新排序后继续

## 示例

```
## Phase 0: 问题分析

当前: create_window(x=0, y=0) 创建窗口在主屏左上角
期望: 窗口创建在鼠标光标所在屏幕的中心
差距: x/y 硬编码为 0，没有获取光标屏幕的逻辑

## Phase 1: 变更定位

文件: desktop_main.py
1. main(): L475-L477 — create_window 的 x=0, y=0 参数
2. 新增函数 _get_cursor_screen_center() — 计算光标屏幕中心坐标
3. _show_window(): L355-L361 — 托盘恢复时同样用了主屏居中

## Phase 2: 变更点详述

变更点 1: 提取光标屏幕中心计算函数
文件: desktop_main.py
位置: 新增，紧接 _wnd_proc_ref = None 之后 (L395)
之前: (新增，无)
之后:
def _get_cursor_screen_center():
    try:
        cursor = win32api.GetCursorPos()
        monitor = win32api.MonitorFromPoint(cursor, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(monitor)
        ml, mt, mr, mb = info["Monitor"]
        cx = ml + (mr - ml - WINDOW_W) // 2
        cy = mt + (mb - mt - WINDOW_H) // 2
    except:
        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
        cx = (sw - WINDOW_W) // 2
        cy = (sh - WINDOW_H) // 2
    return cx, cy
依赖: 无

变更点 2: create_window 使用光标屏幕坐标
文件: desktop_main.py
位置: main() L475-L477
之前:
        x=0,
        y=0,
之后:
        x=init_cx,
        y=init_cy,
依赖: 变更点 1

## Phase 3: 实施顺序

Phase 0: 变更点 1（新增函数）
Phase 1: 变更点 2（修改 create_window 参数）
```
