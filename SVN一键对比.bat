@echo off
setlocal enabledelayedexpansion
title SVN 一键对比工具

:: 用 PowerShell 获取正确格式的今天日期
for /f "delims=" %%d in ('powershell -command "Get-Date -Format 'yyyy-MM-dd'"') do set TODAY=%%d

set WORKSPACE=C:\Users\admin\.qclaw\workspace
set DEFAULT_OUTPUT=%WORKSPACE%\svn_compare_result.xlsx

echo ============================================
echo       SVN 一键对比工具
echo ============================================
echo 说明：查询 SVN 提交记录 - 查找上一版本 - 对比差异
echo 输出格式：Sheet, ID, SC, SubstituteId, 当前版本, 上一版本, 操作类型
echo.

set /p SVN_URL="SVN 仓库路径或URL (必填): "
if "%SVN_URL%"=="" (
    echo [错误] 必须提供 SVN 仓库路径或URL！
    pause
    exit /b 1
)

set /p START_DATE="请输入开始日期 (格式: YYYY-MM-DD，留空默认2024-01-01): "
set /p END_DATE="请输入结束日期 (格式: YYYY-MM-DD，留空默认今天): "
set /p KEYWORDS="请输入关键词 (多个用空格分隔，留空则显示全部): "
set /p AUTHOR="请输入提交者过滤 (留空则不限制): "
set /p OUTPUT_FILE="输出文件路径 (留空默认 %DEFAULT_OUTPUT%): "
set /p WORKERS="下载并发数 (留空默认 6): "
set /p PARSE_WORKERS="解析并发数 (留空默认 8): "

if "%START_DATE%"=="" set START_DATE=2024-01-01
if "%END_DATE%"=="" set END_DATE=%TODAY%
if "%OUTPUT_FILE%"=="" set OUTPUT_FILE=%DEFAULT_OUTPUT%
if "%WORKERS%"=="" set WORKERS=6
if "%PARSE_WORKERS%"=="" set PARSE_WORKERS=8

echo.
echo 正在执行，请稍候...
echo ============================================

set PYTHON=python
where python >nul 2>&1
if errorlevel 1 (
    set PYTHON=py
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found!
        pause
        exit /b 1
    )
)

REM 构建关键词参数
set KEY_PARAMS=
if not "%KEYWORDS%"=="" (
    for %%k in (%KEYWORDS%) do set KEY_PARAMS=!KEY_PARAMS! -k %%k
)

REM 构建完整命令
set "CMD=%PYTHON% "%WORKSPACE%\svn_oneclick_compare.py" -u "%SVN_URL%" -s "%START_DATE%" -e "%END_DATE%" %KEY_PARAMS%"

if not "%AUTHOR%"=="" set "CMD=%CMD% --author %AUTHOR%"
set "CMD=%CMD% -o "%OUTPUT_FILE%" -w %WORKERS% -p %PARSE_WORKERS%"

REM 执行
%CMD%

echo.
echo ============================================
echo 完成！按任意键退出...
pause >nul
