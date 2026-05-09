@echo off
echo 检查系统环境...
echo %PATH%
echo.
echo Python 版本:
python --version 2>&1
echo.
echo SVN 版本:
svn --version 2>&1
echo.
echo 测试完成
pause
