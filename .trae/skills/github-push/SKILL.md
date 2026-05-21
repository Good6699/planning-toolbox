---
name: "github-push"
description: "一键将本地修改提交并推送到 GitHub。Invoke when user asks to push/commit/sync changes, upload to GitHub, or save work remotely."
---

# github-push — 一键推送修改到 GitHub

## 工作流概述

```
用户说"push/推送/提交/上传"→ 本 Skill 接管：
  ① git status 列出变更
  ② 用户确认 commit message（遵循 Conventional Commits）
  ③ 可选：flake8 语法检查
  ④ git add -A + git commit
  ⑤ git push origin web-optimal
```

## 执行步骤

### Step 0: 确认意图

先问用户要提交的变更内容和 commit message 描述，不要直接提交。

同时也问用户是否需要跑 flake8 检查（默认跑）。

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

### Step 3: flake8 检查（可选）

```powershell
flake8 .
```

如果有 E/F 级别错误，列出来让用户决定修复还是跳过。

### Step 4: 提交并推送

```powershell
git add -A
git commit -m "<type>(<scope>): <subject>"
git push origin web-optimal
```

### Step 5: 汇报结果

显示 push 成功的输出信息。如果有冲突或失败，提示用户处理。

## 注意事项

- 分支是 `web-optimal`（当前工作分支）
- remote 已配好 token，不需要手动输入密码
- `_github_push.py` 是旧版完整初始化的脚本，日常用本 Skill 三步搞定
- push 失败时先检查网络，确认 `git pull` 之后再试
