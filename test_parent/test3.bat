@echo off
chcp 936
setlocal EnableDelayedExpansion
title File Org Tool

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

set "target="
set "found=0"

if exist "!parent!\!name!" (set "target=!parent!\!name!" & set "found=1")

if !found!==0 (
    for /d /r "!parent!" %%d in (*) do (
        if /i "%%~nxd"=="!name!" set "target=%%~fd"
    )
    if defined target set "found=1"
)

if !found!==1 (echo Found: !target! & copy /y "!inp!" "!target!\") else (echo Not found)

pause