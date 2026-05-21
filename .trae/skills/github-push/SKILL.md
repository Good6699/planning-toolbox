---
name: "github-push"
description: "一键提交本地修改到 Git（不再推送 GitHub）。Invoke when user asks to commit/save/submit changes."
---

# github-push — 本地提交（不再上传 GitHub）

> ⚠️ 已弃用远程推送，改为纯本地版本管理。此 skill 只做 `git status` + `git add` + `git commit`。

## 工作流概述

```
用户说"提交/保存"→ 本 Skill 接管：
  ① git status 列出变更
  ② 用户确认 commit message（遵循 Conventional Commits）
  ③ git add + git commit（--no-verify 跳过 flake8）
```

## 执行步骤

### Step 0: 确认意图

先问用户要提交的变更内容和 commit message 描述，不要直接提交。

### Step 1: 查看变更

```powershell
git status
git diff --stat
```

列出所有变更文件，让用户看到要提交的内容。

### Step 2: 构建 commit message

参考已有的 git 提交规范：

```
<type>(<scope>): <subject>
```

| type | 含义 |
|------|------|
| feat | 新功能 |
| fix | 修复 Bug |
| refactor | 重构 |
| perf | 性能优化 |
| style | 代码格式 |
| docs | 文档/规则 |
| chore | 杂项/配置 |
| test | 测试 |

常用 scope：`web`(前端), `gui`(桌面端), `cmp`(对比), `config`, `rules`, `deps`

subject 用中文、祈使句、不加句号。

### Step 3: 提交

```powershell
git commit --no-verify -m "<type>(<scope>): <subject>"
```

## 注意事项

- 纯本地版本管理，不再推送到 GitHub
- remote origin 仍保留但不再主动 push
- 使用 `--no-verify` 跳过 pre-commit 的 flake8 检查（已有规则保持不变）
- 需要查看历史：`git log --oneline`
- 需要回退版本：`git reset --soft HEAD~1`

- 分支是 `web-optimal`（当前工作分支）
- `_github_push.py` 是旧版脚本，已无实际用途
