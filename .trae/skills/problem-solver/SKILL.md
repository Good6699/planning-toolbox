---
name: "problem-solver"
description: "Structured root cause analysis using Fishbone diagram + 5 Whys. PROACTIVELY invoke when diagnosing bugs, unexpected behavior, or when user's problem statement lacks root cause — do NOT skip directly to code changes."
---

# Problem Solver

Structured root cause analysis before any fix. 强制先找根因，再讨论修复。

## Core Principle

> **没有确认根因的修复方案是猜。** 永远不要先改代码再分析。

## Process

### ⚠️ 读图谱报告：定位问题涉及的模块和文件

在开始任何问题分析之前，**必须先读 graphify 图谱报告**：

1. 使用 `Read` 工具打开 `graphify-out/GRAPH_REPORT.md`
2. 查阅 **核心模块、社区分组** 两个章节，了解代码全局结构
3. 在**社区分组**中找到问题相关功能所属的社区，确认涉及的上下游文件和模块
4. 在**代码文件结构**中找到相关文件，确认关联节点数
5. **不得跳过此步骤**，图谱能揭示 SearchCodebase 搜不到的跨文件关联关系

### Phase 1: Define the Problem

回答四个问题：

| 问题 | 说明 |
|------|------|
| **当前行为是什么？** | 客观描述，不带判断 |
| **期望行为是什么？** | 可测试、可验证的结论 |
| **触发条件是什么？** | 用户做了什么操作？环境是什么？ |
| **差距在哪里？** | 当前与期望之间差了什么？ |

输出：一段清晰的 **"问题陈述"**。

### Phase 2: 5 Whys 根因挖掘

从问题表象出发，连续追问"为什么"，每层必须基于**代码证据**或**日志事实**：

```
Why 1: [直接原因 — 表面现象]
  证据: [代码行、日志、行为]

Why 2: [深层原因 — 为什么直接原因存在]
  证据: [代码行、函数调用链]

Why 3: [更深处 — 为什么深层原因存在]
  证据: [...]

Why 4: [接近根因]
  证据: [...]

Why 5: [根因 — 可行动的根因]
  证据: [...]
```

当"5"找到可行动的根本原因时停止。可行动 = 可以通过代码变更、配置变更或流程变更消除。

### Phase 3: 鱼骨图（可选，用于复杂问题）

当问题涉及多个维度时，从以下维度分析潜在原因：

| 维度 | 关注点 |
|------|--------|
| **人 (Man)** | 使用方式、理解偏差 |
| **机器 (Machine)** | 窗口系统、消息机制 |
| **方法 (Method)** | 代码逻辑、处理流程 |
| **测量 (Measurement)** | 行为验证方式 |

### Phase 4: 根因确认

- 根因断言：一段话说明"最终根因是 X"
- 证据链：汇总 Phase 2 中的关键证据
- 可验证性：如果修复了 X，问题应该消失

### Phase 5: 修复建议（仅陈述，不执行）

列出可能的修复方向，标注 trade-off。不改代码。

## 使用规则

1. **必须完成 Phase 1-4 才能进入 Phase 5**
2. Phase 5 只陈述方案，不修改代码
3. 如果问题涉及多个子系统，对每个子系统独立做 5 Whys
4. 证据不足时停止并说明"缺少什么证据"
