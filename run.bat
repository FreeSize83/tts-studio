@echo off
setlocal
cd /d "%~dp0"
title TTS Studio

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3.10+ not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    pause
    exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.10 or newer is required.
    %PY% --version
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)

set "VPY=.venv\Scripts\python.exe"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

"%VPY%" -c "import PyQt6.QtMultimedia, requests, numpy, miniaudio, lameenc" >nul 2>nul
if errorlevel 1 (
    echo [2/3] Installing dependencies: PyQt6, requests, numpy, miniaudio, lameenc ...
    "%VPY%" -m pip install --no-cache-dir --upgrade pip
    "%VPY%" -m pip install --no-cache-dir "PyQt6>=6.5" "requests>=2.28" numpy miniaudio lameenc
    if errorlevel 1 goto :fail
)

echo [3/3] Starting TTS Studio ...
"%VPY%" tts_studio.py
if errorlevel 1 (
    echo.
    echo [ERROR] The app exited with an error - see the messages above.
    pause
)
exit /b 0

:fail
echo.
echo [ERROR] Installation failed - see the messages above.
pause
exit /b 1
