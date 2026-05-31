@echo off
cd /d "%~dp0"
echo ============================================================
echo   Planning Toolbox - One Click Build
echo   PyInstaller + Update Zip + APPDATA Deploy
echo ============================================================
echo.

echo [1/3] PyInstaller packaging...
python build.py
if %errorlevel% neq 0 (
    echo [ERROR] Build failed, check log above
    pause
    exit /b 1
)

echo.
echo [2/3] Generating update zip + MD5...
python dist_update.py
if %errorlevel% neq 0 (
    echo [ERROR] Update zip generation failed
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo   Output: ..\dist\PlanningToolbox\
echo   Update: ..\update-server\PlanningToolbox_{v}.zip
echo.
echo   To start update server:
echo     cd ..\update-server
echo     python -m http.server 8080
echo.
pause
