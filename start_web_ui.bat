@echo off
chcp 65001 > nul
title TaikoNation Web UI Server
echo ========================================================
echo       TaikoNation v1.0 - Web UI Launcher
echo ========================================================
echo.

cd /d "%~dp0"

set PYTHON_EXE=C:\Users\user\AppData\Local\Python\bin\python.exe

if not exist "%PYTHON_EXE%" (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set PYTHON_EXE=python
    ) else (
        echo [ERROR] Python not found.
        pause
        exit /b 1
    )
)

echo [INFO] Using Python: %PYTHON_EXE%

if not exist "output\model\taiko_nation_pytorch.pt" (
    echo [INFO] Converting model weights to PyTorch format...
    "%PYTHON_EXE%" convert_weights.py
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Model conversion failed.
        pause
        exit /b 1
    )
)

echo [INFO] Starting TaikoNation Web Server at http://127.0.0.1:8000 ...
echo [INFO] Press Ctrl+C in this window to stop the server.
echo.

start "" "http://127.0.0.1:8000"
"%PYTHON_EXE%" server.py

pause
