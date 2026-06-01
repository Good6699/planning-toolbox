@echo off
setlocal enabledelayedexpansion
for /f "tokens=*" %%a in ('type "%~dp0_update_args.txt" 2^>nul') do (
    if "!ZIP_FILE!"=="" (set ZIP_FILE=%%a) else if "!TMP_DIR!"=="" (set TMP_DIR=%%a) else set APP_NAME=%%a
)
set EXE_NAME=%APP_NAME%.exe

if "%ZIP_FILE%"=="" exit /b 1

ping 127.0.0.1 -n 4 >nul

taskkill /f /im "%EXE_NAME%" >nul 2>&1
ping 127.0.0.1 -n 2 >nul

powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TMP_DIR%' -Force" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    powershell -Command "$s=New-Object -ComObject Shell.Application;$z=$s.NameSpace('%ZIP_FILE%');$d=$s.NameSpace('%TMP_DIR%');$d.CopyHere($z.Items(),16)"
)

for %%i in ("%~dp0..") do set APP_DIR=%%~fi\

xcopy /E /Y /Q "%TMP_DIR%\%APP_NAME%\*" "%APP_DIR%" >nul 2>&1

rd /S /Q "%TMP_DIR%" >nul 2>&1
del /F /Q "%ZIP_FILE%" >nul 2>&1
del /F /Q "%~dp0_update_args.txt" >nul 2>&1

start "" "%APP_DIR%%EXE_NAME%"

exit /b 0
