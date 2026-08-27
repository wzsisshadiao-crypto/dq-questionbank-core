@echo off
rem Double-click launcher for the DQ QuestionBank local workspace.
rem Requires Python 3.10 or newer, either via the Windows "py" launcher or on PATH.
setlocal
cd /d "%~dp0"

set "launcher="
where py >nul 2>nul
if not errorlevel 1 set "launcher=py -3"
if not defined launcher (
    where python >nul 2>nul
    if not errorlevel 1 set "launcher=python"
)
if not defined launcher (
    echo Python was not found on this machine.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo then double-click this file again.
    pause
    exit /b 1
)

%launcher% run.py %*
if errorlevel 1 pause
endlocal
