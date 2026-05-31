---
name: "build-dist"
description: "Builds 策划工具箱 into a distributable exe directory using PyInstaller. Invoke when user says '打包' or 'build' or '编译' or '生成exe'."
---

# Build Dist — 策划工具箱 PyInstaller 打包

一键将策划工具箱打包为可分发目录 `dist/策划工具箱/`（同时创建 `dist/策划工具箱_v1.0_时间戳/` 归档）。

## 前置条件

- 已安装 PyInstaller：`pip install pyinstaller`
- `toolbox_core/build.py` 存在且语法正确
- workspace 根目录的 `main.py`（入口文件）存在
- `_cmp_worker.py`、`_merge_analyzer.py`、`_export_error_code_erl.py`、`_merge_analyze_worker.py` 四个 worker 脚本存在于 workspace 根目录（PyInstaller 不会自动追踪子进程脚本）

## 执行步骤

### Step 1: 检查环境

```powershell
pip list 2>nul | findstr PyInstaller
```

如果没找到，自动安装：
```powershell
pip install pyinstaller
```

### Step 2: 检查 worker 脚本

检查 workspace 根目录是否存在以下文件：
- `_cmp_worker.py`
- `_merge_analyzer.py`
- `_export_error_code_erl.py`
- `_merge_analyze_worker.py`

如果缺失，用 `SearchCodebase` 搜索项目中是否存在这些文件，并用 `Glob` 查找。如果存在但不在 workspace 根目录，记录路径待检查 `build.py` 中的引用路径是否匹配。

### Step 3: 语法验证

```powershell
cd toolbox_core
python -m py_compile build.py
```

失败则修正后重试。

### Step 4: 执行打包

```powershell
cd toolbox_core
python build.py
```

过程：
1. `build.py` 自动清理旧构建缓存（删除 `build/`、`.spec` 文件）
2. 去掉 API Key 后复制 `svn_gui_config.json`
3. 运行 PyInstaller（`--onedir` 模式），固定输出到 `dist/策划工具箱/`（exe 文件名始终不变）
4. 用 copytree 创建 `dist/策划工具箱_v1.0_时间戳/` 归档
5. 复制 `update_version.py` 到打包目录的 `_internal/toolbox_core/` 下
6. 自动部署到 `%APPDATA%/planning-toolbox/策划工具箱/`

### Step 5: 验证打包结果

检查最新输出目录：
```powershell
Get-ChildItem dist | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

检查关键文件：
- `策划工具箱.exe`（主程序，在时间戳目录中）
- `_internal/`（依赖库目录）
- `_internal/toolbox_core/`（核心模块，含 update_version.py 和 svn_gui_config.json）

### Step 6: 统计输出

```powershell
$latest = Get-ChildItem dist | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$f = Get-ChildItem -Recurse $latest.FullName
Write-Host "$($f.Count) 个文件, $('{0:N1}' -f (($f | Measure-Object -Sum Length).Sum/1MB)) MB"
```

### Step 7: 告知用户打包完成

如果指定了 `--zip` 参数，告知用户：
- 目录包路径：`dist/策划工具箱/`
- 更新包路径：`update-server/策划工具箱_vX.X.zip`
- 服务器启动命令：`cd update-server && python -m http.server 8080`

如果只打包未生成 zip，提示用户加 `--zip` 参数可在打包的同时生成更新包。

## 流程图

```
[用户: 打包]
    │
    ▼
[Step 1: 检查 PyInstaller 安装]
    │  └─ 未安装 → pip install pyinstaller
    │
    ▼
[Step 2: 检查 worker 脚本]
    │
    ▼
[Step 3: 语法检查 python build.py]
    │
    ▼
[Step 4: python build.py]
    │  ├─ 清理旧构建
    │  ├─ 去掉 API Key 复制配置
    │  ├─ PyInstaller 打包
    │  └─ 复制 update_version.py
    │
    ▼
[Step 5: 验证输出]
    │
    ▼
[Step 6: 统计 + 告知用户]
```

## 注意事项

- `build.py` 的 `APP_VERSION` **自动从 `toolbox_core/update_version.py` 读取**，无需手动修改。先用 `push-update` skill 改好版本号，再调用本 skill 打包即可
- 因此**调用本 skill 前必须先调 `push-update`** 更新版本号，否则打出来的包版本号还是旧的
- `svn_gui_config.json` 中的 `tr_api_key_enc`/`tr_api_key` 字段会被 `build.py` 自动移除
- `.gitignore` 排除了 `dist/`、`build/`、`*.spec`，这些文件不会进入 Git
- 打包后的 exe 是 `--onedir` 模式（目录包），解压即用，无需安装
- 如果打包后 exe 启动报 `ModuleNotFoundError`，需要用 `--hidden-import` 补充依赖，或确认 `--add-data` 路径正确
