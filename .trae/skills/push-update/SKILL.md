---
name: "push-update"
description: "Auto-increments version, pushes version.json to update-server, and commits to git. Invoke when user says '推送更新' or 'push update' or '发新版'."
---

# Push Update — 策划工具箱推送更新

一键完成：版本号自增 → 生成 version.json → Git 提交

## 执行步骤

> **⚠️ 如果用户需要同时打包和推送，必须先调用 `build-dist` skill 完成打包，再回到本 skill 推送版本信息。本 skill 不执行打包。**

### Step 0: 确认版本号变更类型

读取 `toolbox_core/update_version.py` 中的 `APP_VERSION`（如 `"v1.0"`）。
使用 `AskUserQuestion` tool 询问用户：

**问题 1**: 版本号怎么变？
- `patch` — 修 Bug 级别：`v1.0` → `v1.0.1`
- `minor` — 新功能级别：`v1.0` → `v1.1`
- `major` — 大版本：`v1.0` → `v2.0`
- 自定义输入

**问题 2**: 是否强制推送？
- `force: true` — 客户端必须更新才能用
- `force: false` — 可推迟（默认）

**问题 3**: 更新说明（release notes）？
- 让用户输入说明文字

### Step 1: 更新版本号

改 `toolbox_core/update_version.py`：
```python
import socket
APP_VERSION = "v1.0"           # ← 改这里
_HOSTNAME = socket.gethostname()
UPDATE_URL = f"http://{_HOSTNAME}:8080/update/"
```

解析当前版本号 `v{major}.{minor}.{patch}`，按选择类型自增：

| 类型 | v1.0 → | v1.0.1 → | v1.1 → |
|------|--------|----------|--------|
| patch | v1.0.1 | v1.0.2 | v1.1.1 |
| minor | v1.1 | v1.1.0 | v1.2 |
| major | v2.0 | v2.0.0 | v2.0 |

用 `SearchReplace` 工具修改 `APP_VERSION` 行。

### Step 2: 语法验证

```powershell
cd toolbox_core
python -m py_compile update_version.py
```

失败则修正后重试。

### Step 3: 更新 version.json

读取 `update-server/version.json` 中的旧的 `version` 字段，与新的 `APP_VERSION` 比较：

| 情况 | 说明 | 处理方式 |
|------|------|---------|
| `旧 version ≠ 新 APP_VERSION` | 之前已推送过同系列版本（如 v1.0→v1.1），`update-server/` 下有对应的 zip 包 | 读旧 version.json 的 `md5` 和 `url` 复用 |
| `旧 version = 新 APP_VERSION` | 全新推送，`update-server/` 下没有对应版本的 zip 包 | `md5` 填空字符串 `""`，`url` 填 `"策划工具箱_{新版本}.zip"` |
| 旧 `version.json` 不存在 | 首次推送 | 同上，全新推送 |

读取旧 version.json：
```powershell
Get-Content update-server/version.json -Raw | ConvertFrom-Json
```

用 `SearchReplace` 或 `Write` 工具写入新的 `update-server/version.json`：

```json
{
  "version": "v1.1",
  "url": "策划工具箱_v1.1.zip",
  "md5": "",
  "notes": "用户输入的更新说明",
  "force": false
}
```

> `md5` 留空是因为本 skill 不做打包，实际 zip 包的 MD5 需在手动 `build.py --zip` 生成后再补填。

### Step 4: Git 提交

```powershell
git add toolbox_core/update_version.py update-server/version.json
git commit --no-verify -m "feat: 发布 vX.X"
```

### Step 5: 从最新包生成更新 zip

用 `python dist_update.py` 从 `dist/策划工具箱/`（现有打包目录）直接生成 zip + 补填 MD5，**不需要重新 PyInstaller**（省时 ~5 分钟）。

```powershell
cd toolbox_core
python dist_update.py
```

该命令会：
1. 从 `dist/策划工具箱/_internal/toolbox_core/` 读取现有打包文件
2. 版本号优先用 **工作区的 `update_version.py`**（刚推送的新版本号）
3. 生成 `update-server/策划工具箱_v1.0.3.zip`
4. 计算 MD5 并补填到 `update-server/version.json`

### Step 6: 告知用户

告知用户：
- 新版本号
- 是否强制推送
- 更新包已就绪，启动 HTTP 服务即可推送：
  ```
  cd update-server
  python -m http.server 8080
  ```

## 流程图

```
[用户: 推送更新]
    │
    ▼
[Step 0: 问版本号类型、是否强制、更新说明]
    │
    ▼
[Step 1: 改 update_version.py 版本号]
    │
    ▼
[Step 2: 语法检查]
    │
    ▼
[Step 3: 生成 version.json]
    │
    ▼
[Step 4: Git commit]
    │
    ▼
[Step 5: python dist_update.py 生成 zip + 补 MD5]
    │
    ▼
[Step 6: 启动 HTTP 服务推送]
```

## 注意事项

- 本 skill **不做打包**，只推送版本信息。打包需要单独执行 `build-dist` 或 `python build.py`
- version.json 的 `url` 字段指向 `update-server/` 下的 zip 包名，需与手动打包后的 zip 包名一致
- `.bat` 文件和 `.exe` 被 `.gitignore` 排除，但本 skill 不涉及这些文件
- **不要 commit `dist/` 目录**（已被 .gitignore 排除）
