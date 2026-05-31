@echo off
cd /d "%~dp0..\update-server"
echo ============================================================
echo   Planning Toolbox - Update Server
echo ============================================================
echo.
echo   Server started at:
echo     http://localhost:8080/
echo     http://%COMPUTERNAME%:8080/
echo.
echo   To stop: close this window or press Ctrl+C
echo.
echo   Files served:
dir /b *.zip version.json 2>nul
echo.
echo ============================================================
echo.
python -m http.server 8080
echo.
pause
