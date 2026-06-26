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
- 修改了服务器配置（`update-server/version.json` / `UPDATE_URL` 配置 / `build.py` 打包地址）后
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

### Step 3: 同步最新配置到仓库（优先用 Python 校验后写入，避免乱码）

提交前先将运行时配置（`%APPDATA%/planning-toolbox/svn_gui_config.json`）同步到仓库，确保 GitHub 上的配置是最新的。

**重要：必须用 Python 校验 JSON 有效性后再写入。** 直接 PowerShell 复制可能把已损坏的 JSON（如 `tr_lang_id_map` 未闭合字符串）同步到仓库，导致后续 `json.load()` 报错打包失败。

```powershell
# 用 Python 读取 APPDATA 配置，校验 JSON 有效性后再写入（避免乱码同步到仓库）
$cfg = Get-Content "$env:APPDATA\planning-toolbox\svn_gui_config.json" -Raw
$out = "$PWD\toolbox_core\svn_gui_config.json"
python -c @"
import json, sys
with open(r'$env:APPDATA\planning-toolbox\svn_gui_config.json', 'rb') as f:
    raw = f.read()
try:
    data = json.loads(raw.decode('utf-8'))
    # 写回标准化 JSON（缩进 2，ensure_ascii=False，UTF-8 无 BOM）
    with open(r'$out', 'w', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
    print('OK: 配置已校验并写入')
except json.JSONDecodeError as e:
    print(f'WARN: APPDATA 配置已损坏（{e}），跳过同步，保留仓库版本')
"@
```

注意：**禁止用 PowerShell 的 `[System.IO.File]::WriteAllText()` 直接写入 JSON 文件**——它不校验 JSON 有效性，会直接把损坏内容写到仓库。

### Step 4: 提交本地 Git（有代码变更时）

```powershell
git status
git add <files>
git commit --no-verify -m "<type>: <中文描述>"
```

- type 用 `fix` / `feat` / `refactor` / `style` / `docs` / `chore` 之一
- 描述用中文、祈使句
- 提交前先确认变更文件列表

**打包相关文件的特殊处理**：
- `toolbox_core/svn_gui_config.json` 配置文件的变更必须显式 `git add`（被 `.gitignore` 排除或不在追踪中时需要 `-f`）
- `toolbox_core/build.py`、`toolbox_core/update_version.py` 需要显式 `git add`
- `update-server/version.json` 和 `update-server/*.zip` 需要显式 `git add -f`（被 `.gitignore` 排除，必须强制添加）
- `toolbox_core/_updater.bat` 需要 `git add -f`（`.gitignore` 排除了 `*.bat`）
- 子进程生产脚本 `_cmp_worker.py`、`_merge_analyzer.py`、`_merge_analyze_worker.py`、`_export_error_code_erl.py` 需要 `git add -f`（被 `_*.py` 规则排除，但已加 `.gitignore` 例外）
- `.trae/skills/build-dist/` 和 `.trae/skills/push-update/` 两个 skill 目录需要显式 `git add`
- `dist/`、`build/`、`*.spec` 不要提交（已被 `.gitignore` 排除）

**服务器配置相关注意事项**：
- `update_version.py` 中的 `UPDATE_URL` 决定了客户端从哪个地址检查更新。如果服务器 IP 或计算机名变了，必须修改此文件并重新打包
- `update-server/version.json` 中的 `force` 字段控制是否强制推送（`true`=必须更新才能用，`false`=可推迟）
- `update-server/version.json` 中的 `md5` 字段是更新 zip 包的 MD5 校验值，`build.py --zip` 会自动计算
- 发布新版本后需要启动 HTTP 服务：`cd update-server && python -m http.server 8080`
- 防火墙需放行 8080 端口：`netsh advfirewall firewall add rule name="策划工具箱更新服务" dir=in action=allow protocol=TCP localport=8080`

### Step 5: 告知用户

一句话告知完成：图谱更新结果 + 记录/提交情况。若打包或服务器配置相关文件有变更，额外告知用户：
- 打包脚本已更新，如需重新打包执行 `cd toolbox_core && python build.py --zip`
- 服务器配置已更新（`UPDATE_URL` / `version.json`），如需发布新版记得启动 HTTP 服务
- 启动 HTTP 服务：`cd update-server && python -m http.server 8080`

## 注意事项

- Step 1（图谱更新）自动跳过无变更情况，无变更时输出 "No changes since last build. Skipping."
- 如果增量更新报错，加 `--full --no-viz` 做全量重建
- Step 2-3（记录+提交）可根据情况选择性执行，不是每次都必须
- 不要记琐碎操作，只记有价值的经验和教训
- Git 提交使用 `--no-verify`
- 当前分支 `web-optimal`，纯本地版本管理
