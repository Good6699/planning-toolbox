---
name: "record-and-commit"
description: "将经验教训写入 MEMORY.md 知识库 + 提交本地 Git。Invoke when user says 记下来/提交/保存/save/commit or after fixing a complex bug."
---

# record-and-commit — 记录知识库 + 本地版本提交

## 触发时机

用户说 `记下来` / `提交` / `保存` / `commit` / `save`，或解决完一个复杂问题后。

## 执行步骤

### Step 1: 写入 MEMORY.md（仅当有经验要记录时）

追加到 `MEMORY.md` 的 `## 经验与决策` 节，格式为：

```
### 问题简短标题
- **场景**：一句话描述
- **根因**：……
- **解决方案**：改了什么、怎么改的
- **涉及文件**：[filename](file:///path)
```

总结根因和解决方案即可，不用问用户确认。

### Step 2: 提交本地 Git（仅当有代码变更时）

```powershell
git status
git add <files>
git commit --no-verify -m "<type>: <中文描述>"
```

type 用 `fix` / `feat` / `refactor` / `style` / `docs` / `chore` 之一，描述用中文、祈使句。

### Step 3: 告知用户

一句话告知完成。

## 注意事项

- 不要记琐碎操作，只记有价值的经验和教训
- Git 提交使用 `--no-verify`
- 当前分支 `web-optimal`，纯本地版本管理
