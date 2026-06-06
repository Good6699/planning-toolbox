@echo off
setlocal enabledelayedexpansion
set DEB=%~dp0_update_debug.txt
echo [%DATE% %TIME%] bat start > "%DEB%"
echo [%DATE% %TIME%] dp0=%~dp0 >> "%DEB%"

set /a LN=0
for /f "tokens=*" %%a in ('type "%~dp0_update_args.txt" 2^>nul') do (
    set /a LN+=1
    if !LN!==1 set ZIP_FILE=%%a
    if !LN!==2 set TMP_DIR=%%a
    if !LN!==3 set APP_NAME=%%a
    if !LN!==4 set APP_DIR=%%a
)
set EXE_NAME=%APP_NAME%.exe
if not "!APP_DIR:~-1!"=="\" set APP_DIR=!APP_DIR!\
echo [%DATE% %TIME%] LN=%LN% ZIP_FILE=!ZIP_FILE! >> "%DEB%"
echo [%DATE% %TIME%] TMP_DIR=!TMP_DIR! >> "%DEB%"
echo [%DATE% %TIME%] APP_NAME=!APP_NAME! >> "%DEB%"
echo [%DATE% %TIME%] APP_DIR=!APP_DIR! >> "%DEB%"
echo [%DATE% %TIME%] EXE_NAME=!EXE_NAME! >> "%DEB%"

if "%ZIP_FILE%"=="" exit /b 1

echo [%DATE% %TIME%] taskkill /f /im !EXE_NAME! >> "%DEB%"
taskkill /f /im "%EXE_NAME%" 2>&1 >> "%DEB%"
set /a WAIT_TOTAL=0
:wait_loop
ping 127.0.0.1 -n 4 >nul
set /a WAIT_TOTAL+=3
tasklist /fi "IMAGENAME eq %EXE_NAME%" 2>nul | find /i "%EXE_NAME%" >nul
if errorlevel 1 (
    echo [%DATE% %TIME%] process gone after !WAIT_TOTAL!s >> "%DEB%"
    goto update_ok
)
if !WAIT_TOTAL! geq 15 (
    echo [%DATE% %TIME%] timeout !WAIT_TOTAL!s >> "%DEB%"
    goto update_fail
)
echo [%DATE% %TIME%] waiting !WAIT_TOTAL!s >> "%DEB%"
goto wait_loop

:update_fail
rd /S /Q "%TMP_DIR%" >nul 2>&1
del /F /Q "%ZIP_FILE%" >nul 2>&1
del /F /Q "%~dp0_update_args.txt" >nul 2>&1
echo [%DATE% %TIME%] update_fail >> "%DEB%"
exit /b 1

:update_ok
echo [%DATE% %TIME%] unzip >> "%DEB%"
powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TMP_DIR%' -Force" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [%DATE% %TIME%] powershell unzip fail, fallback Shell.Application >> "%DEB%"
    powershell -Command "$s=New-Object -ComObject Shell.Application;$z=$s.NameSpace('%ZIP_FILE%');$d=$s.NameSpace('%TMP_DIR%');$d.CopyHere($z.Items(),16)"
)

echo [%DATE% %TIME%] APP_DIR=!APP_DIR! >> "%DEB%"
echo [%DATE% %TIME%] src=!TMP_DIR!\!APP_NAME!\* >> "%DEB%"
echo [%DATE% %TIME%] dst=!APP_DIR! >> "%DEB%"
dir "!TMP_DIR!\!APP_NAME!" >> "%DEB%" 2>&1

xcopy /E /Y /Q "%TMP_DIR%\%APP_NAME%\*" "%APP_DIR%"
echo [%DATE% %TIME%] xcopy1 ec=!ERRORLEVEL! >> "%DEB%"
if errorlevel 1 (
    ping 127.0.0.1 -n 4 >nul
    xcopy /E /Y /Q "%TMP_DIR%\%APP_NAME%\*" "%APP_DIR%"
    echo [%DATE% %TIME%] xcopy2 ec=!ERRORLEVEL! >> "%DEB%"
)

echo [%DATE% %TIME%] cleanup >> "%DEB%"
rd /S /Q "%TMP_DIR%" >nul 2>&1
del /F /Q "%ZIP_FILE%" >nul 2>&1
del /F /Q "%~dp0_update_args.txt" >nul 2>&1

echo [%DATE% %TIME%] start new: !APP_DIR!!EXE_NAME! >> "%DEB%"
start "" "%APP_DIR%%EXE_NAME%"

echo [%DATE% %TIME%] bat done >> "%DEB%"
exit /b 0
