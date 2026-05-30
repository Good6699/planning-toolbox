---
name: "push-update"
description: "Builds new version with PyInstaller, auto-increments version, pushes update package to update-server. Invoke when user says '推送更新' or 'push update' or '发新版'."
---

# Push Update — 策划工具箱推送更新

一键完成：版本号自增 → PyInstaller 打包 → 生成更新包和 version.json → 更新服务器就绪

## 执行步骤

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

### Step 3: 执行 PyInstaller 打包 + 生成更新包

```powershell
cd toolbox_core
python build.py --zip
```

`build.py` 会自动：
1. 清理旧构建文件
2. 去掉 API Key 再复制配置
3. 运行 PyInstaller (`--onedir` 模式)
4. 复制无 API Key 的 `svn_gui_config.json` 到打包目录
5. 压缩为 `策划工具箱_vX.X.zip`
6. 计算 MD5
7. 生成 `update-server/version.json`

### Step 4: 修改生成的 version.json

`build.py` 生成的 `update-server/version.json` 中 `force` 默认为 `false`。
用 `SearchReplace` 修改 `force` 为用户选择的值。
用 `SearchReplace` 修改 `notes` 为用户输入的更新说明。

手工检查 version.json：
```json
{
  "version": "v1.1",
  "url": "策划工具箱_v1.1.zip",
  "md5": "a1b2c3d4...",
  "notes": "修复了XXX，新增了XXX",
  "force": true
}
```

### Step 5: Git 提交

```powershell
git add toolbox_core/update_version.py update-server/version.json update-server/策划工具箱_v*.zip toolbox_core/build.py
git commit --no-verify -m "feat: 发布 vX.X"
```

### Step 6: 告知用户更新服务器已就绪

告知用户：
- 新版本号
- 是否强制推送
- 更新服务器启动命令
- 更新服务器地址

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
[Step 3: python build.py --zip]
    │  ├─ PyInstaller 打包 dist/
    │  └─ 生成 update-server/策划工具箱_vX.X.zip
    │     └─ 生成 update-server/version.json
    │
    ▼
[Step 4: 修改 version.json 的 force 和 notes]
    │
    ▼
[Step 5: Git commit]
    │
    ▼
[Step 6: 告诉用户服务器就绪]
```

## 注意事项

- 确保已安装 PyInstaller：`pip install pyinstaller`
- `build.py` 会在 workspace 根目录生成 `dist/策划工具箱/` 完整可分发目录
- 更新 zip 包和 `version.json` 都在 `update-server/` 目录下
- 用户启动 HTTP 服务：`cd update-server && python -m http.server 8080`
- 如遇到 build.py 报错，检查是否缺 `_cmp_worker.py` 等 worker 脚本（它们被 `.gitignore` 排除，需要从 git 历史恢复或确认存在）
- **不要 commit `dist/` 目录**（已被 .gitignore 排除）
- `.bat` 文件和 `.exe` 被 `.gitignore` 排除，需要用 `git add -f` 强制添加
