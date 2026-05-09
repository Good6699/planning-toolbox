@echo off
chcp 65001 >nul
echo ===============================================
echo 环境检查脚本
echo ===============================================
echo.
echo 1. 检查系统环境变量...
echo 系统PATH:
echo %PATH%
echo.
echo 2. 检查Python安装...
python --version 2>&1
echo Python路径:
where python 2>&1
echo.
echo 3. 检查SVN安装...
svn --version 2>&1
echo SVN路径:
where svn 2>&1
echo.
echo 4. 检查Python依赖...
echo 已安装的包:
pip list
echo.
echo 5. 检查工作目录...
echo 当前目录: %CD%
echo 工作目录文件:
dir /b
echo.
echo ===============================================
echo 环境检查完成
echo ===============================================
pause