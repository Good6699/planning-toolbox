@echo off
title Ce Hua Gong Ju Xiang - Env Fix Tool
setlocal enabledelayedexpansion

set "WORKSPACE=%~dp0"
set "WORKSPACE=%WORKSPACE:~0,-1%"

echo =============================================
echo        Ce Hua Gong Ju Xiang
echo        Environment Setup Tool
echo =============================================
echo.
echo Checking environment...

rem ==============================================
rem  Step 1: Check Python
rem ==============================================
echo.
echo [1/3] Checking Python...

set PYTHON_EXE=
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where python') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if defined PYTHON_EXE (
    echo   [OK] Python found: %PYTHON_EXE%
    for /f "tokens=2" %%v in ('"%PYTHON_EXE%" --version 2^>^&1') do echo   Version: %%v
    goto :check_svn
)

echo   [FAIL] Python not found.
echo.
echo   This tool requires Python 3.10+.
echo.
echo   Options:
echo     [1] Auto-download and install Python 3.13
echo     [2] Skip (I will install Python later)
echo.
set /p "PY_CHOICE=Enter 1 or 2 (default 1): "
if "!PY_CHOICE!"=="2" goto :check_svn

echo   Downloading Python 3.13 (about 30MB)...
call :download_python
if %errorlevel% neq 0 (
    echo   [FAIL] Download failed.
    echo   Please manually download from: https://www.python.org/downloads/
    pause
    exit /b
)

echo   Installing Python (silent)...
start /wait "" "%TEMP%\python-3.13.3-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_tkinter=1
if %errorlevel% equ 0 (
    echo   [OK] Python installed successfully.
    echo   Please close this window and restart the toolbox.
) else (
    echo   [WARN] Install may have failed (code: %errorlevel%).
    echo   Please manually install: https://www.python.org/downloads/
)
pause
exit /b

:check_svn
echo.

rem ==============================================
rem  Step 2: Check SVN
rem ==============================================
echo [2/3] Checking SVN client...

set SVN_EXE=
where svn >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where svn') do (
        if not defined SVN_EXE set "SVN_EXE=%%i"
    )
)

if defined SVN_EXE (
    echo   [OK] SVN found: %SVN_EXE%
    for /f "delims=" %%v in ('"%SVN_EXE%" --version -q 2^>^&1') do echo   Version: %%v
    goto :check_done
)

echo   [FAIL] SVN client not found.
echo.
echo   SVN is required for svn log, upload, and workflow features.
echo.
echo   Options:
echo     [1] Auto-download and install SlikSvn
echo     [2] Skip (I will install SVN later)
echo.
set /p "SVN_CHOICE=Enter 1 or 2 (default 1): "
if "!SVN_CHOICE!"=="2" goto :check_done

call :download_svn
if %errorlevel% neq 0 (
    echo   [FAIL] SVN download failed.
    echo   Please manually install: https://sliksvn.com/download/
    echo   Or install TortoiseSVN with command line tools.
    pause
    exit /b
)

echo   Installing SlikSvn (admin rights required)...
msiexec /i "%TEMP%\SlikSvn-1.14.4.2511-x64.msi" /quiet /norestart INSTALLDIR="C:\Program Files\SlikSvn"
if %errorlevel% equ 0 (
    echo   [OK] SlikSvn installed successfully.
) else (
    echo   [WARN] Install may have failed (code: %errorlevel%).
    echo   Please manually install: https://sliksvn.com/download/
)
pause
exit /b

:check_done
echo.

rem ==============================================
rem  Step 3: Run deep check + launch
rem ==============================================
echo [3/3] Running deep environment check...

if defined PYTHON_EXE (
    if exist "%WORKSPACE%\setup_checker.py" (
        "%PYTHON_EXE%" "%WORKSPACE%\setup_checker.py" --dir "%WORKSPACE%"
        if %errorlevel% equ 0 (
            echo   [OK] Environment check passed.
        ) else (
            echo   [WARN] Environment check completed with warnings.
        )
    ) else (
        echo   [WARN] setup_checker.py not found, skipping.
    )
) else (
    echo   [WARN] Python not installed, skipping deep check.
)

echo.

rem ==============================================
rem  Launch
rem ==============================================
if defined PYTHON_EXE (
    echo Starting toolbox...
    start "" "%PYTHON_EXE%" "%WORKSPACE%\svn_launcher.py" --dir "%WORKSPACE%"
    echo   [OK] Toolbox launched.
) else (
    echo =============================================
    echo   Setup incomplete.
    echo   Please install Python 3.13 and try again.
    echo   Or run "ce hua gong ju xiang GUI.vbs" again.
    echo =============================================
    pause
)
exit /b

rem ==============================================
rem  Functions
rem ==============================================
:download_python
    set "OUT=%TEMP%\python-3.13.3-amd64.exe"
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe', '%OUT%')" >nul 2>&1
    if exist "%OUT%" exit /b 0
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe', '%OUT%')" >nul 2>&1
    if exist "%OUT%" exit /b 0
    exit /b 1

:download_svn
    set "OUT=%TEMP%\SlikSvn-1.14.4.2511-x64.msi"
    echo   Downloading SlikSvn...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://sliksvn.com/pub/SlikSvn-1.14.4.2511-x64.msi', '%OUT%')" >nul 2>&1
    if exist "%OUT%" exit /b 0
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://sliksvn.com/pub/SlikSvn-1.14.4.2511-x64.msi', '%OUT%')" >nul 2>&1
    if exist "%OUT%" exit /b 0
    exit /b 1
