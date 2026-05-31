@echo off
cd /d "%~dp0..\update-server"
echo ============================================================
echo   Planning Toolbox - Update Server
echo ============================================================
echo.

if not exist version.json (
    echo [WARNING] version.json not found!
    echo   Run build_all.bat first to generate the update package.
    echo.
    pause
    exit /b 1
)

echo Current version info:
echo.
python -c "
import json
with open('version.json', encoding='utf-8') as f:
    v = json.load(f)
print(f'  Version: {v.get(\"version\", \"?\")}')
print(f'  Package: {v.get(\"url\", \"?\")}')
print(f'  MD5:     {v.get(\"md5\", \"?\")[:16]}...')
print(f'  Force:   {v.get(\"force\", False)}')
print(f'  Notes:   {v.get(\"notes\", \"\")}')
"
echo.
if exist *.zip (
    for %%f in (*.zip) do (
        call :size "%%f"
    )
) else (
    echo  [WARNING] No zip package found! Clients will see version info but cannot download.
)
echo.

set /p confirm="Push this update? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo.
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo ============================================================
echo   Server started at:
echo     http://localhost:8080/
echo     http://%COMPUTERNAME%:8080/
echo.
echo   To stop: close this window or press Ctrl+C
echo ============================================================
echo.
python -m http.server 8080
echo.
pause
exit /b 0

:size
set SIZEF=%~z1
set /a SIZEMB=%SIZEF% / 1048576
echo   %~nx1 (%SIZEMB% MB)
goto :eof
