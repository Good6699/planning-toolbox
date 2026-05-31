@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   策划工具箱 — 一键打包
echo   本脚本自动执行：PyInstaller 打包 → 生成更新 zip → 部署到 APPDATA
echo ============================================================
echo.

echo [1/3] PyInstaller 打包...
python build.py
if %errorlevel% neq 0 (
    echo [错误] 打包失败，请查看上方日志
    pause
    exit /b 1
)

echo.
echo [2/3] 生成更新 zip + 补 MD5...
python dist_update.py
if %errorlevel% neq 0 (
    echo [错误] 生成更新包失败
    pause
    exit /b 1
)

echo.
echo [3/3] 完成！
echo.
echo   输出目录: ..\dist\策划工具箱\
echo   更新包:   ..\update-server\策划工具箱_版本.zip
echo.
echo   启动推送:
echo     cd ..\update-server
echo     python -m http.server 8080
echo.
pause
