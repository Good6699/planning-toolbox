@echo off
cd /d "%~dp0"
echo ============================================================
echo   Planning Toolbox - One Click Build
echo   Auto version patch + PyInstaller + Update Zip
echo ============================================================
echo.

echo [1/2] Auto-patch version + PyInstaller packaging...
python build.py --auto-patch --zip
if %errorlevel% neq 0 (
    echo [ERROR] Build failed, check log above
    pause
    exit /b 1
)

echo.
echo [2/2] Done!
echo.
echo   Output: ..\dist\策划工具箱\ (renamed to timestamp dir)
echo   Update: ..\update-server\策划工具箱_{v}.zip
echo.
echo   To start update server:
echo     double-click serve_update.bat
echo.
pause
