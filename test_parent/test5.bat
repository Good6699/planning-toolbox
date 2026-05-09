@echo off
chcp 936
setlocal EnableDelayedExpansion

if "%~1"=="" (echo No input & pause & exit)

set "inp=%~1"
for %%i in ("%~1") do set "name=%%~ni"

echo Input: !inp!
echo Name: !name!

pushd "%~dp0.."
set "parent=%CD%"
popd

echo Parent: !parent!

if not exist "!parent!" (echo Parent not exist & pause & exit)

set "found=0"

if exist "!parent!\!name!" (set "found=1" & echo Found in parent)

if !found!==0 (
    for /d /r "!parent!" %%d in (*) do (
        if /i "%%~nxd"=="!name!" (set "found=1" & echo Found: %%~fd)
    )
)

if !found!==1 (
    if exist "!parent!\!name!\" (
        copy /y "!inp!" "!parent!\!name!\" 
    ) else (
        for /d /r "!parent!" %%d in (*) do if /i "%%~nxd"=="!name!" copy /y "!inp!" "%%~fd\"
    )
    echo Done
) else (echo Not found)

pause