@echo off
setlocal

set SCRIPT_DIR=%~dp0
set SCRIPT=%SCRIPT_DIR%build.py

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 "%SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

echo Error: Python 3 is required to run the dissertation build pipeline.
exit /b 1
