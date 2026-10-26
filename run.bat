@echo off
rem Double-click to run MediaGala. First run sets up the environment.
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo Creating virtual environment...
    py -3 -m venv .venv >nul 2>&1 || python -m venv .venv >nul 2>&1
    if not exist "%VENV_PY%" (
        echo.
        echo Python was not found. Install Python 3.11+ from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH" during installation.
        pause
        exit /b 1
    )
)

if not exist ".venv\.installed" (
    echo Installing dependencies, this only happens once...
    "%VENV_PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Installing dependencies failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
    type nul > ".venv\.installed"
)

"%VENV_PY%" run.py
pause
