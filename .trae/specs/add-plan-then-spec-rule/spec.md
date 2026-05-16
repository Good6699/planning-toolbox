# 执行完 plan 后使用 /spec 规则

## Why

当前流程要求改代码前必须 `/plan`，但 plan 确认后缺少结构化的实施指引（tasks.md + checklist.md），容易遗漏步骤或偏离计划。需要补充 `/spec` 作为 plan 确认后的标准下一步。

## What Changes

- 在 `AGENTS.md` 的 `/plan 前置规则` 段落中追加：plan 确认后 → 调用 `/spec` 进入 Spec 模式
- 明确 plan 和 spec 的职责分工：`/plan` 定方向，`/spec` 定细节 + 执行

## Impact

- Affected specs: 无（新建）
- Affected code: 仅 `AGENTS.md`（文档修改，属于例外场景，可直接编辑）

## ADDED Requirements

### Requirement: plan → spec 串行流程

系统 SHALL 在 plan 确认后自动进入 spec 模式。

#### Scenario: 正常流程
- **WHEN** 用户确认 plan
- **THEN** 立即调用 `/spec` 进入 Spec 模式
- **THEN** 在 Spec 模式下编写 spec.md / tasks.md / checklist.md
- **THEN** 调用 NotifyUser 等待用户确认 spec
- **THEN** 用户确认后开始按 checklist 实施

#### Scenario: 简单任务跳过
- **WHEN** 任务极简单（如改一行配置）
- **THEN** 用户可明确说"不用 spec"
- **THEN** 跳过 spec 阶段，直接执行
