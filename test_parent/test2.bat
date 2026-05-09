@echo off
chcp 936
setlocal EnableDelayedExpansion
title 文件整理工具
echo ============================
echo   拖动文件或文件夹到本脚本
echo ============================
if "%~1"=="" (echo 请拖入文件或文件夹 & pause & exit)
set "inp=%~1"
for %%i in ("%~1") do set "name=%%~ni"
echo 输入文件: !inp!
echo 文件名: !name!
pushd "%~dp0.."
set "parent=%CD%"
popd
echo 目标目录: !parent!
if not exist "!parent!" (echo 父目录不存在 & pause & exit)
set "target="
set "found=0"
if exist "!parent!\!name!" (set "target=!parent!\!name!" & set "found=1")
if !found!==0 (
    for /d /r "!parent!" %%d in (*) do (
        if /i "%%~nxd"=="!name!" set "target=%%~fd"
    )
    if defined target set "found=1"
)
if !found!==1 (echo 找到: !target! & copy /y "!inp!" "!target!\") else (echo 未找到同名文件夹)
pause