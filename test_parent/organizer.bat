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
    echo Parent not found, selecting...
    for /f "delims=" %%d in ('mshta "javascript:var f=new ActiveXObject('Shell.Application').BrowseForFolder(0,'Select target folder',0);if(f)try{new ActiveXObject('Scripting.FileSystemObject').GetStandardStream(1).Write(f.Self.Path)}catch(e){};close();" 1^>nul') do set "parent=%%d"
    if "!parent!"=="" (echo Cancelled & pause & exit /b)
    echo Selected: !parent!
)

:process_args
if "%~1"=="" goto done

set "inp=%~1"
set "is_folder=0"
if exist "%inp%\" set "is_folder=1"

:: Extract name
if !is_folder!==1 (
    for %%i in ("%inp%") do set "name=%%~nxi"
    set "name=%name:~0,-1%"
) else (
    for %%i in ("%inp%") do set "name=%%~ni"
)

echo Input: !inp!
echo Name: !name!

:: Search for matching folder
set "target="
set "found=0"

if exist "!parent!\!name!\" (
    set "target=!parent!\!name!"
    set "found=1"
    echo Found in parent
)

if !found!==0 (
    for /d /r "!parent!" %%d in (*) do (
        if /i "%%~nxd"=="!name!" (
            set "target=%%d"
            set "found=1"
            echo Found: %%d
        )
    )
)

:: Copy if found
if !found!==1 (
    if !is_folder!==1 (
        xcopy /e /i /y "!inp!" "!target!\" >nul
    ) else (
        copy /y "!inp!" "!target!\" >nul
    )
    echo Copied to: !target!
) else (
    echo Not found: !name!
)

shift
goto process_args

:done
echo Done
pause