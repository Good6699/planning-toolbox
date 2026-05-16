# SVN 输入框 UX 增强 Spec

## Why
当前策划工具箱 Web 界面中 SVN 地址输入框和输出目录输入框缺少拖拽文件夹、自动识别 SVN 仓库、一键打开文件夹等便捷操作。输入内容也不会自动保存，日期选择按钮在深色主题下难以辨识。

## What Changes
- `svn_url` 输入框支持拖拽文件夹，自动调用 `svn info` 识别远程仓库 URL
- `svn_url` 旁边新增 "打开" 按钮，用资源管理器打开当前输入路径
- `svn_url` 和 `svn_output` 输入框内容自动保存（失焦/输入时触发）
- 日期选择器 `::-webkit-calendar-picker-indicator` 图标提亮

## Impact
- Affected specs: 无（纯 UI 增强）
- Affected code: `templates/index.html`（JS + CSS + HTML）、`web_app.py`（新增 1 路由）

## ADDED Requirements

### Requirement: SVN URL 输入框拖拽文件夹自动识别仓库
系统 SHALL 在用户拖拽文件夹到 SVN 地址输入框时，自动调用后端 `svn info --show-item url` 获取该文件夹对应 SVN 仓库的远程 URL 并填入输入框。

#### Scenario: 拖入 SVN 工作副本文件夹
- **WHEN** 用户将 SVN 工作副本文件夹拖入 `svn_url` 输入框
- **THEN** 前端调 `POST /api/svn/detect`，后端执行 `svn info --show-item url`，返回仓库 URL
- **THEN** 输入框填入返回的远程 URL

#### Scenario: 拖入非 SVN 文件夹
- **WHEN** 用户将非 SVN 文件夹拖入 `svn_url` 输入框
- **THEN** 后端返回空或错误，前端以 toast 提示 "该文件夹不是 SVN 工作副本"

### Requirement: SVN URL 输入框新增 "打开" 按钮
系统 SHALL 在 `svn_url` 输入框旁边提供 "打开" 按钮，点击时：若当前值是有效本地路径则用资源管理器打开；若是 URL 则忽略。

#### Scenario: 打开本地路径
- **WHEN** 用户点击 "打开" 按钮且当前值为有效本地路径
- **THEN** 调用 `POST /api/open/folder` 打开资源管理器

#### Scenario: 当前值为非本地路径
- **WHEN** 用户点击 "打开" 按钮且当前值为 URL
- **THEN** 前端静默忽略，不做任何操作

### Requirement: 输入框内容自动保存
系统 SHALL 在 `svn_url` 和 `svn_output` 输入框失去焦点（blur）时自动将当前内容保存到对应历史记录，不再依赖 Enter 键或任务执行才保存。

#### Scenario: 输入后失焦
- **WHEN** 用户在 `svn_url` 输入框编辑后点击其他区域（失焦）
- **THEN** 内容自动写入 `svn_urls` 列表且置顶去重

#### Scenario: 已有 Enter 键逻辑不冲突
- **WHEN** 用户按 Enter 键（已有逻辑）或失焦
- **THEN** 两次保存操作去重后结果一致，不会产生重复条目

### Requirement: 日期选择器按钮提亮
系统 SHALL 为 `input[type="date"]` 指定 `::-webkit-calendar-picker-indicator` 样式，使用 CSS `invert(1)` filter 或自定义浅色 SVG 图标，确保在深色背景 `#0e1219` 上清晰可见。

#### Scenario: 日期按钮可见
- **WHEN** 用户在 SVN 页签查看日期范围输入框
- **THEN** 右侧日历图标为浅色/白色，在深色背景上清晰可辨
