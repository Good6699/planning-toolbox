---
name: "record-and-commit"
description: "将经验教训写入 MEMORY.md 知识库 + 提交本地 Git。Invoke when user says 记下来/提交/保存/save/commit or after fixing a complex bug."
---

# record-and-commit — 记录知识库 + 本地版本提交

## 触发时机

在以下场景**必须**调用本 Skill：

1. **用户说**：`记下来`、`记录下来`、`写到知识库`、`提醒以后`、`避免再踩坑`
2. **用户说**：`提交`、`保存`、`commit`、`save`、`上传`
3. **解决完一个复杂问题后**：根因确认 + 修复完成后，主动问用户"要不要记到知识库再加个版本？"
4. **反复踩坑**：同一个问题修了两三次以上，必须记录教训 + 提交

## 执行步骤

### Step 1: 如果是"记录到知识库"，先确认要记录的内容

总结本次记录需要包含的要素：

| 要素 | 说明 |
|------|------|
| 日期 | `YYYY-MM-DD` |
| 问题 | 一句概括（什么功能、什么问题） |
| 根因 | Why 分析的最终结论 |
| 解决方案 | 改了什么、怎么改的 |
| 涉及文件 | 修改了哪些文件 |

### Step 2: 写入 MEMORY.md

追加到 `MEMORY.md` 的 `## 经验与决策` 节，格式为：

```
- **问题标题**：YYYY-MM-DD 一句话描述问题
  - **根因**：……
  - **解决方案**：……
  - **涉及文件**：[filename](file:///path)
```

如果有更通用的"最佳实践"，可以单独作为一个独立条目，使用粗体标题。

### Step 3: 更新知识图谱

```powershell
$env:PYTHONPATH="c:\Users\admin\.qclaw\workspace\py_modules"; C:\Users\admin\AppData\Local\Programs\Python\Python313\python.exe -m graphify update .
```

### Step 4: 如果是"提交版本"，执行本地 Git 提交

#### 4a: 查看变更

```powershell
git status
git diff --stat
```

让用户看到要提交的文件。

#### 4b: 构建 commit message

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

subject 用中文、祈使句、不加句号。

#### 4c: 提交

```powershell
git add <files>
git commit --no-verify -m "<type>(<scope>): <subject>"
```

### Step 5: 告知用户

告知用户已完成，并附上记录摘要或提交信息。

## 注意事项

- 知识库记录只记录**有价值的经验和教训**，不要记琐碎日常操作
- 根因要写**可行动的结论**，不要写"粗心"、"没注意"这类无意义描述
- 解决方案要**具体到代码/配置/流程**层面
- Git 提交使用 `--no-verify` 跳过 flake8 pre-commit 检查
- 纯本地版本管理，不再推送到 GitHub
- 当前分支：`web-optimal`
