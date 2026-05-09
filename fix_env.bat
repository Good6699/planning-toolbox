@echo off
chcp 65001 >nul

set "PYTHON_PATH=C:\Users\admin\AppData\Local\Programs\Python\Python313"
set "PYTHON_SCRIPTS=%PYTHON_PATH%\Scripts"

rem 设置正确的环境变量
set "PATH=%PYTHON_PATH%;%PYTHON_SCRIPTS%;%PATH%"

echo ===============================================
echo 环境修复脚本
echo ===============================================
echo 设置Python路径为: %PYTHON_PATH%
echo.
echo 1. 检查Python版本...
python --version
echo.
echo 2. 检查pip版本...
pip --version
echo.
echo 3. 安装必要的依赖...
pip install --upgrade pip
echo.
echo 4. 验证依赖安装...
pip list
echo.
echo ===============================================
echo 环境修复完成
echo ===============================================
pause