@echo off
setlocal enabledelayedexpansion
title SVN һ���Աȹ���

:: �� PowerShell ��ȡ��ȷ��ʽ�Ľ�������
for /f "delims=" %%d in ('powershell -command "Get-Date -Format 'yyyy-MM-dd'"') do set TODAY=%%d

set WORKSPACE=C:\Users\admin\.qclaw\workspace
set DEFAULT_OUTPUT=%WORKSPACE%\svn_compare_result.xlsx

echo ============================================
echo       SVN һ���Աȹ���
echo ============================================
echo ˵������ѯ SVN �ύ��¼ - ������һ�汾 - �ԱȲ���
echo �����ʽ��Sheet, ID, SC, SubstituteId, ��ǰ�汾, ��һ�汾, ��������
echo.

set /p SVN_URL="SVN �ֿ�·����URL (����): "
if "%SVN_URL%"=="" (
    echo [����] �����ṩ SVN �ֿ�·����URL��
    pause
    exit /b 1
)

set /p START_DATE="�����뿪ʼ���� (��ʽ: YYYY-MM-DD������Ĭ��2024-01-01): "
set /p END_DATE="������������� (��ʽ: YYYY-MM-DD������Ĭ�Ͻ���): "
set /p KEYWORDS="������ؼ��� (����ÿո�ָ�����������ʾȫ��): "
set /p AUTHOR="�������ύ�߹��� (����������): "
set /p OUTPUT_FILE="����ļ�·�� (����Ĭ�� %DEFAULT_OUTPUT%): "
set /p WORKERS="���ز����� (����Ĭ�� 6): "
set /p PARSE_WORKERS="���������� (����Ĭ�� 8): "

if "%START_DATE%"=="" set START_DATE=2024-01-01
if "%END_DATE%"=="" set END_DATE=%TODAY%
if "%OUTPUT_FILE%"=="" set OUTPUT_FILE=%DEFAULT_OUTPUT%
if "%WORKERS%"=="" set WORKERS=6
if "%PARSE_WORKERS%"=="" set PARSE_WORKERS=8

echo.
echo ����ִ�У����Ժ�...
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

REM �����ؼ��ʲ���
set KEY_PARAMS=
if not "%KEYWORDS%"=="" (
    for %%k in (%KEYWORDS%) do set KEY_PARAMS=!KEY_PARAMS! -k %%k
)

REM ������������
set "CMD=%PYTHON% "%WORKSPACE%\svn_oneclick_compare.py" -u "%SVN_URL%" -s "%START_DATE%" -e "%END_DATE%" %KEY_PARAMS%"

if not "%AUTHOR%"=="" set "CMD=%CMD% --author %AUTHOR%"
set "CMD=%CMD% -o "%OUTPUT_FILE%" -w %WORKERS% -p %PARSE_WORKERS%"

REM ִ��
%CMD%

echo.
echo ============================================
echo ��ɣ���������˳�...
pause >nul
