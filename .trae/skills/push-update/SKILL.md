---
name: "push-update"
description: "读取已打包版本，提交到 Git 并启动更新服务器。打包请先运行 build_all.bat。"
---

# Push Update — 策划工具箱推送更新

打包和推送已分离：
- **打包** → 双击 `toolbox_core/build_all.bat`（自动版本号 +1 + PyInstaller + zip）
- **推送** → 本 skill 读取已打包的版本号，提交到 Git + 启动服务器

## 执行步骤

### Step 0: 确认推送参数

从 `update-server/version.json` 读取当前版本号和配置，询问用户：

**问题 1**: 是否强制推送？
- `force: true` — 客户端必须更新才能用
- `force: false` — 可推迟（默认）

**问题 2**: 更新说明（release notes）？
- 让用户输入说明文字

### Step 1: 更新 version.json 的 force 和 notes

保留已有字段（`version`、`url`、`md5`），只更新用户确认的 `force` 和 `notes`。

### Step 2: Git 提交

```powershell
git add toolbox_core/update_version.py update-server/version.json
git commit --no-verify -m "feat: 发布 vX.X"
```

### Step 3: 启动更新服务器

```powershell
start "" python -m http.server 8080
```

或告知用户双击 `toolbox_core/serve_update.bat`。

### Step 4: 告知用户

- 版本号：从 version.json 读取
- 是否强制
- 更新说明
- 服务器已就绪
