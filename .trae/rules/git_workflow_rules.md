# Git 提交规范与代码质量工作流

## 概述

本项目使用 Git + GitHub 进行版本管理，要求每次代码提交都遵循统一的规范流程，确保代码质量和提交历史的可读性。本文档定义了完整的提交工作流。

---

## 一、提交信息规范（Conventional Commits）

所有 commit message 必须严格遵循以下格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 1.1 Header（必需）

**格式：** `<type>(<scope>): <subject>`

- `type` 和 `subject` 之间**必须有冒号和空格**
- Header 总长度建议 ≤ 50 字符（非强制但推荐）
- `subject` 使用祈使句、中文描述、不加句号

#### type（提交类型）

| type | 含义 | 说明 |
|------|------|------|
| `feat` | 新功能 | 新增业务功能或特性 |
| `fix` | 修复 Bug | 修复代码缺陷 |
| `refactor` | 重构 | 不改变功能的前提下重构代码 |
| `perf` | 性能优化 | 优化性能或资源占用 |
| `style` | 代码格式 | 缩进、空格、标点等非逻辑变更 |
| `docs` | 文档 | 注释、README、规则文件等 |
| `chore` | 杂项 | 构建配置、依赖更新、工具链等 |
| `test` | 测试 | 增删改测试用例 |
| `ci` | CI/CD | 持续集成配置变更 |
| `revert` | 回滚 | 撤销之前的提交 |

#### scope（影响范围，可选）

用括号包裹，表示本次修改影响的功能模块。本项目常用 scope：

| scope | 对应模块 |
|-------|---------|
| `web` | Web 应用端（web_app.py + templates） |
| `gui` | 桌面 GUI 端（desktop_main.py + toolbox_tab_*） |
| `cmp` | SVN 对比核心（svn_oneclick_compare.py） |
| `worker` | 子进程对比（_cmp_worker.py） |
| `export` | 导出模式 |
| `config` | 配置文件 |
| `rules` | 项目规则文档 |
| `deps` | 依赖管理 |

#### subject（描述）

简洁说明本次修改做了什么，中文描述，动词开头。示例：
- ✅ `feat(web): 新增版本对比结果的排序功能`
- ✅ `fix(cmp): 修复日期范围查询时版本号溢出的问题`
- ✅ `perf(worker): 优化 SS 指纹预检正则性能`
- ✅ `refactor(web): 拆分对比结果渲染函数`

### 1.2 Body（可选，复杂修改时必填）

说明**为什么改**而非**怎么改**，空一行后接正文。

### 1.3 Footer（可选）

关联 Issue 或标注破坏性变更：

```
Closes #123
BREAKING CHANGE: xxxxxx
```

### 1.4 完整示例

```
feat(web): 新增版本筛选功能

支持按作者、日期范围、关键词筛选版本列表
解决了大批量版本时页面卡顿的问题

Closes #42
```

---

## 二、代码规范检查规则

### 2.1 检查工具

本项目使用 **flake8**（集成 pycodestyle + pyflakes + mccabe）作为代码静态检查工具。

### 2.2 检查规则配置

见项目根目录 `.flake8` 文件：

```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503, E501
exclude = .git,__pycache__,build,dist,venv,.venv,__byte_cache__,临时辅助文件
max-complexity = 15
```

| 规则 | 说明 |
|------|------|
| max-line-length = 120 | 行宽上限 120 字符（适配本项目长参数） |
| extend-ignore = E203, W503 | E203（冒号前空格冲突）、W503（行续符） |
| max-complexity = 15 | 函数圈复杂度上限 15 |

### 2.3 手动执行检查

```bash
# 检查单个文件
flake8 svn_oneclick_compare.py

# 检查整个项目
flake8 .

# 语法快速验证（不启动 flake8 也行）
python -m py_compile svn_oneclick_compare.py
```

### 2.4 检查通过标准

- 不允许有 **E/F** 级别错误（语法/逻辑错误）
- 圈复杂度超过 15 的 C901 必须重构后方可提交
- W 级别警告允许存在但应尽量修复

---

## 三、提交前强制流程

每次提交代码（`git commit`）前，**必须按以下顺序执行**：

### 3.1 流程图

```
[修改代码]
    │
    ▼
[Step 1: 语法检查] python -m py_compile <修改的文件>
    │
    ▼
[Step 2: 规范检查] flake8 <修改的文件>
    │
    ▼
[Step 3: 写 commit message] 遵循 type(scope): subject 格式
    │
    ▼
[Step 4: git commit]
    │
    ▼
[Step 5: git push]
```

### 3.2 pre-commit 钩子（自动执行）

项目已配置 Git pre-commit 钩子，在 `.git/hooks/pre-commit`，会在 `git commit` 时自动：

1. 检查暂存区是否有 .py 文件
2. 对暂存区 .py 文件运行 flake8
3. 如果 flake8 检测到 E/F 级别错误，**阻止提交**
4. 如果检测到 W 级别警告，**提示但不阻止**

### 3.3 手动跳过检查（仅限紧急情况）

```bash
git commit --no-verify -m "fix: 紧急修复线上崩溃"
```

⚠️ **注意：** `--no-verify` 仅限紧急 bug 修复，常规提交不得使用。

---

## 四、版本策略与标签管理

### 4.1 语义化版本

本项目采用语义化版本号：`v<major>.<minor>.<patch>`

| 版本位 | 变化条件 | 示例 |
|--------|---------|------|
| major | 不兼容的架构变更/重大重构 | v2.0 |
| minor | 新增功能/模块 | v1.1 |
| patch | Bug 修复/性能优化 | v1.0.1 |

### 4.2 里程碑版本

**里程碑版本**指的是一个可发布的功能完整版本，需满足以下条件之一：
- 完成了可独立使用的新功能模块
- 架构有重大改进
- 准备提交到 GitHub 作为可展示版本

### 4.3 创建里程碑版本

```bash
# 1. 确保工作区干净
git status

# 2. 提交所有改动
git add .
git commit -m "chore: v1.0 版本发布准备"

# 3. 打标签
git tag v1.0

# 4. 推送标签到 GitHub
git push origin v1.0

# 5. 推送代码
git push origin web-optimal
```

### 4.4 Tag 命名规则

- 里程碑版本：`v1.0`, `v1.1`, `v2.0`
- 补丁版本：`v1.0.1`, `v1.0.2`
- 预发布版本：`v2.0-beta.1`, `v2.0-rc.1`

### 4.5 GitHub Release 配合

打完 tag 后，在 GitHub 仓库页面：
1. 进入 **Releases** → **Create a new release**
2. 选择对应的 tag
3. Release title 写：`v1.0 Web 应用版`
4. Description 写该版本的变更要点

---

## 五、分支策略

### 5.1 分支结构

```
main              ─── 稳定发布版（对应里程碑 tag）
  └── web-optimal ─── Web 应用开发主分支（当前工作分支）
```

### 5.2 分支命名

- `main` — 生产稳定分支，只合并不直接开发
- `web-optimal` — Web 应用端特性开发（当前使用）
- 如需新建功能分支：`feature/<功能名>`（如 `feature/add-sort`）
- 修复分支：`fix/<问题描述>`（如 `fix/date-overflow`）

### 5.3 合并策略

- 功能分支开发完成后，先 rebase 到 web-optimal，再合并
- main 分支的合并只在里程碑版本时进行

---

## 六、提交工作流总结

### 日常开发流程

```bash
# Step 1: 修改代码
# (修改 web_app.py 或其他文件)

# Step 2: 语法检查（必须）
python -m py_compile web_app.py

# Step 3: 规范检查（必须）
flake8 web_app.py

# Step 4: 如果有错误，修复后重复 Step 2-3

# Step 5: 提交代码（pre-commit 钩子会自动再跑一次检查）
git add web_app.py
git commit -m "feat(web): 新增版本对比结果的排序功能"

# Step 6: 推送到 GitHub
git push origin web-optimal
```

### 发布里程碑流程

```bash
# 完成一个可发布版本后
git tag v1.1
git push origin v1.1
git push origin web-optimal
# 再到 GitHub 创建 Release
```

---

## 七、附则

1. 本文档作为项目级工作流规则，所有代码修改都必须遵守
2. 如用户明确指定"不打里程碑 tag"时，只需走日常开发流程
3. 紧急修复可以通过 `--no-verify` 跳过检查，但事后必须补修代码规范问题
4. 本文档本身使用 `docs(git-workflow)` 的 type 提交
