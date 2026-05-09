@echo off
setlocal EnableDelayedExpansion
chcp 936 >nul
title 文件整理工具

:: 检查输入
if "%~1"=="" (
    echo 请拖动文件或文件夹到本脚本图标上
    pause
    exit /b
)

:: 获取脚本父目录
set "script_dir=%~dp0"
set "script_dir=%script_dir:~0,-1%"
for %%i in ("%script_dir%") do set "parent=%%~dpi"
set "parent=%parent:~0,-1%"

:: 检查父目录是否存在，不存在则弹窗选择
if not exist "%parent%\" (
    echo 父目录不存在，请选择目标目录...
    for /f "delims=" %%d in ('mshta "javascript:var f=new ActiveXObject('Shell.Application').BrowseForFolder(0,'请选择目标目录',0);if(f)try{new ActiveXObject('Scripting.FileSystemObject').GetStandardStream(1).Write(f.Self.Path)}catch(e){};close();" 1^>nul 2^>nul') do set "parent=%%d"
    if "!parent!"=="" (
        echo 未选择目录，退出
        pause
        exit /b
    )
)

:: 处理参数（支持多文件）
:process_args
if "%~1"=="" goto :done

set "inp=%~1"
set "is_folder=0"

:: 判断是文件还是文件夹
if exist "%inp%\" set "is_folder=1"

:: 提取名称
if !is_folder!==1 (
    for %%i in ("%inp%") do set "name=%%~nxi"
) else (
    for %%i in ("%inp%") do set "name=%%~ni"
)

echo.
echo ================================
echo 处理: !name!
echo ================================

:: 搜索同名文件夹
set "target="
set "found=0"

:: 先在父目录直接查找
if exist "!parent!\!name!\" (
    set "target=!parent!\!name!"
    set "found=1"
)

:: 如果没找到，递归搜索子目录
if !found!==0 (
    for /d /r "!parent!" %%d in (*) do (
        if /i "%%~nxd"=="!name!" (
            set "target=%%d"
            set "found=1"
        )
    )
)

:: 找到则复制，否则询问是否选择其他目录
if !found!==1 (
    echo 找到目标文件夹: !target!
    if !is_folder!==1 (
        xcopy /e /i /y "!inp!" "!target!\"
    ) else (
        copy /y "!inp!" "!target!\"
    )
    echo 复制完成
) else (
    echo 未找到同名文件夹: !name!
    choice /c yn /m "是否从历史记录中选择目录?"
    if !errorlevel!==1 (
        call :select_from_history
    )
)

shift
goto :process_args

:done
echo.
echo 所有文件处理完成
pause
exit /b

:select_from_history
set "history_file=%~dp0dir_history.txt"
if not exist "!history_file!" (
    echo 历史记录为空
    exit /b
)

echo 历史目录:
set /a idx=0
for /f "usebackq delims=" %%h in ("!history_file!") do (
    set /a idx+=1
    echo !idx!. %%h
)

if !idx!==0 (
    echo 历史记录为空
    exit /b
)

set /p choice="请输入序号选择目录: "
set /a cnt=0
for /f "usebackq delims=" %%h in ("!history_file!") do (
    set /a cnt+=1
    if !cnt!==!choice! (
        echo 选择: %%h
        if !is_folder!==1 (
            xcopy /e /i /y "!inp!" "%%h\"
        ) else (
            copy /y "!inp!" "%%h\"
        )
        echo 复制完成
    )
)
exit /b