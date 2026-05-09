@echo off
set WORKSPACE=C:\Users\admin\.qclaw\workspace
pythonw "%WORKSPACE%\svn_compare_gui.py"
if errorlevel 1 (
    echo.
    echo [ERROR] 启动失败，请确认 Python 已安装
    pause
)
