@echo off
setlocal EnableDelayedExpansion
chcp 936 >nul

if "%~1"=="" (echo Drag files to this script & pause & exit /b)

:: Get parent directory
set "script_dir=%~dp0"
set "script_dir=%script_dir:~0,-1%"
for %%i in ("%script_dir%") do set "parent=%%~dpi"
set "parent=%parent:~0,-1%"

echo Parent: !parent!

:: Check parent exists
if not exist "%parent%\" (
    echo Parent not found, please select directory...
    for /f "delims=" %%d in ('mshta "javascript:var f=new ActiveXObject('Shell.Application').BrowseForFolder(0,'Select target folder',0);if(f)try{new ActiveXObject('Scripting.FileSystemObject').GetStandardStream(1).Write(f.Self.Path)}catch(e){};close();" 1^>nul') do set "parent=%%d"
    if "!parent!"=="" (echo Cancelled & pause & exit /b)
    echo Selected: !parent!
    call :save_history "!parent!"
)

:process_args
if "%~1"=="" goto done

set "inp=%~1"
set "is_folder=0"
if exist "%inp%\" set "is_folder=1"

:: Extract name
if !is_folder!==1 (
    for %%i in ("%inp%") do set "name=%%~nxi"
    set "name=!name:~0,-1!"
) else (
    for %%i in ("%inp%") do set "name=%%~ni"
)

echo.
echo Processing: !name!

:: Search for matching folder
set "target="
set "found=0"

if exist "!parent!\!name!\" (
    set "target=!parent!\!name!"
    set "found=1"
)

if !found!==0 (
    for /d /r "!parent!" %%d in (*) do (
        if /i "%%~nxd"=="!name!" (
            set "target=%%d"
            set "found=1"
        )
    )
)

:: Copy if found
if !found!==1 (
    echo Found: !target!
    if !is_folder!==1 (
        xcopy /e /i /y "!inp!" "!target!\" >nul
    ) else (
        copy /y "!inp!" "!target!\" >nul
    )
    echo Copied
) else (
    echo Not found: !name!
    call :select_from_history
)

shift
goto process_args

:done
echo.
echo All done
pause
exit /b

:save_history
set "history_file=%~dp0dir_history.txt"
set "new_dir=%~1"
:: Check if already in history
findstr /x /c:"%new_dir%" "!history_file!" >nul 2>&1
if !errorlevel!==0 exit /b
:: Add to history
echo %new_dir%>>"!history_file!"
exit /b

:select_from_history
set "history_file=%~dp0dir_history.txt"
if not exist "!history_file!" (
    echo No history
    exit /b
)

echo.
echo History directories:
set /a idx=0
for /f "usebackq delims=" %%h in ("!history_file!") do (
    set /a idx+=1
    echo !idx!. %%h
    set "dir_!idx!=%%h"
)

if !idx!==0 (
    echo History is empty
    exit /b
)

set /p choice="Select number (or press Enter to skip): "
if "!choice!"=="" exit /b

if defined dir_!choice! (
    set "selected=!dir_%choice%!"
    echo Selected: !selected!
    if !is_folder!==1 (
        xcopy /e /i /y "!inp!" "!selected!\" >nul
    ) else (
        copy /y "!inp!" "!selected!\" >nul
    )
    echo Copied to: !selected!
) else (
    echo Invalid choice
)
exit /b