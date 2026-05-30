---
name: "graphify-and-record"
description: "一键完成知识图谱增量更新 + 记录经验到 MEMORY.md + 本地 Git 提交。改完代码后调用此 skill，依次执行：检测变更→图谱更新→经验记录→Git提交。"
---

# graphify-and-record — 图谱更新 + 经验记录 + Git 提交

合并 `graphify-update` 和 `record-and-commit` 两个技能，一次调用完成：
1. 增量更新知识图谱（graphify_quick.py）
2. 将经验教训写入 MEMORY.md
3. 提交本地 Git

## 触发时机

- 改完代码后需要刷新知识图谱时
- 解决复杂问题后需要记录经验并提交时
- 用户说 `记下来` / `提交` / `保存` / `commit` / `save` 时
- 修改了 `.py` / `.html` / `.js` / `.ts` / `.md` 等正式文件后
- 修改了打包相关文件（`build.py` / `update_version.py` / `_updater.bat` / `build-dist` / `push-update` skill）后
- 修改了 `.gitignore` / `.flake8` / `project_rules.md` 等配置文件后

## 执行步骤

### Step 1: 增量更新知识图谱

`graphify_quick.py` 自动完成检测变更文件 → AST 提取 → 构建 → 聚类 → 生成 GRAPH_REPORT.md 的完整流程。

```powershell
$env:PYTHONPATH="py_modules"; python graphify_quick.py
```

如果输出的节点数异常（如为零或远小于历史值），说明 `.graphifyignore` 过滤有误或前置检测失败。此时可执行全量重建：

```powershell
$env:PYTHONPATH="py_modules"; python graphify_quick.py --full --no-viz
```

### Step 2: 记录经验到 MEMORY.md（有经验需要记录时）

如果有值得记录的经验教训（问题根因、修复方案、架构决策等），追加到 `MEMORY.md` 的 `## 经验与决策` 节，格式为：

```
### 问题简短标题
- **场景**：一句话描述
- **根因**：……
- **解决方案**：改了什么、怎么改的
- **涉及文件**：[filename](file:///path)
```

总结根因和解决方案即可，不用问用户确认。

### Step 3: 提交本地 Git（有代码变更时）

```powershell
git status
git add <files>
git commit --no-verify -m "<type>: <中文描述>"
```

- type 用 `fix` / `feat` / `refactor` / `style` / `docs` / `chore` 之一
- 描述用中文、祈使句
- 提交前先确认变更文件列表

**打包相关文件的特殊处理**：
- `toolbox_core/build.py`、`toolbox_core/update_version.py`、`toolbox_core/update_version.py` 需要显式 `git add`
- `update-server/version.json` 和 `update-server/*.zip` 需要显式 `git add -f`（被 `.gitignore` 排除）
- `toolbox_core/_updater.bat` 需要 `git add -f`（`.gitignore` 排除了 `*.bat`）
- 子进程生产脚本 `_cmp_worker.py`、`_merge_analyzer.py`、`_merge_analyze_worker.py`、`_export_error_code_erl.py` 需要 `git add -f`（被 `_*.py` 规则排除，但已加 `.gitignore` 例外）
- `.trae/skills/build-dist/` 和 `.trae/skills/push-update/` 两个 skill 目录需要显式 `git add`
- `dist/`、`build/`、`*.spec` 不要提交（已被 `.gitignore` 排除）

### Step 4: 告知用户

一句话告知完成：图谱更新结果 + 记录/提交情况。若打包相关文件有变更，额外告知用户打包脚本已更新。如果需要重新打包，告知用户执行 `cd toolbox_core && python build.py --zip`。

## 注意事项

- Step 1（图谱更新）自动跳过无变更情况，无变更时输出 "No changes since last build. Skipping."
- 如果增量更新报错，加 `--full --no-viz` 做全量重建
- Step 2-3（记录+提交）可根据情况选择性执行，不是每次都必须
- 不要记琐碎操作，只记有价值的经验和教训
- Git 提交使用 `--no-verify`
- 当前分支 `web-optimal`，纯本地版本管理
