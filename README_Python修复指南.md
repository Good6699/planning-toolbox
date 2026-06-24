# 📋 Python 环境修复完整指南

## ⚠️ 重要提示

在开始之前，请确保：
1. 您有管理员权限
2. 已经关闭所有正在运行的 Python 程序
3. 已经备份好重要项目（本项目依赖已在 `toolbox_core/py_modules` 中，无需备份）

---

## 🎯 修复方案概览

### 方案 A：使用 Python 3.13（推荐）
我们的打包好的 `策划工具箱.exe` 使用的是 **Python 3.13**，它能完美工作！

**优点：**
- 不需要卸载现有 Python 3.11
- 直接安装一个新的 Python 3.13，两者可以共存
- 我们的程序可以指定使用 Python 3.13 运行

### 方案 B：彻底重新安装 Python 3.11
完全卸载 Python 3.11 后重新安装。

---

## 🚀 推荐方案：安装 Python 3.13（最简单）

### 步骤 1：下载 Python 3.13

访问 Python 官网下载页面：
```
https://www.python.org/downloads/
```

下载 **Python 3.13.x Windows installer (64-bit)**

### 步骤 2：安装 Python 3.13

1. 运行下载的安装程序
2. **重要！** 勾选 **"Add Python 3.13 to PATH"**
3. 点击 **"Install Now"**（默认安装）
4. 等待安装完成

### 步骤 3：修改 `策划工具箱.bat` 使用 Python 3.13

编辑 `策划工具箱.bat`，将：
```batch
set PYTHON_EXE=C:\Program Files\Python311\python.exe
```

改为：
```batch
set PYTHON_EXE=C:\Program Files\Python313\python.exe
```

---

## 🔧 方案 B：彻底重新安装 Python 3.11

### 步骤 1：卸载 Python 3.11

1. 打开 **设置** → **应用** → **已安装的应用**
2. 搜索 "Python"
3. 卸载 **Python 3.11**
4. 卸载 **Python Launcher**（如果有）

### 步骤 2：手动清理残留文件

删除以下目录（如果存在）：
- `C:\Program Files\Python311`
- `C:\Users\Administrator\AppData\Local\Programs\Python\Python311`
- `C:\Users\Administrator\AppData\Roaming\Python`

### 步骤 3：清理环境变量

1. 右键 **此电脑** → **属性** → **高级系统设置** → **环境变量**
2. 在 **用户变量** 和 **系统变量** 中查找包含 "Python" 或 "Python311" 的条目并删除
3. 删除 `Path` 变量中的 Python 相关路径

### 步骤 4：重新下载 Python 3.11

访问：
```
https://www.python.org/downloads/release/python-3119/
```

下载 **Windows installer (64-bit)**

### 步骤 5：安装 Python 3.11

1. 运行安装程序
2. **重要！** 勾选 **"Add Python 3.11 to PATH"**
3. 点击 **"Install Now"**
4. 等待安装完成

---

## ✅ 验证安装

安装完成后，打开新的命令提示符，运行：

```cmd
python --version
```

应该显示：
```
Python 3.13.x
```
或
```
Python 3.11.9
```

然后测试一下：
```cmd
python -c "print('Hello World!')"
```

---

## 📂 项目使用说明

无论使用哪个 Python 版本，我们的项目依赖都已经在 `toolbox_core/py_modules` 目录中，所以不需要再 `pip install` 任何东西！

只需确保 `策划工具箱.bat` 中的 `PYTHON_EXE` 指向正确的 Python 即可。
