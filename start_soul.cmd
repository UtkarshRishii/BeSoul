@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Soul's environment is missing. Run: python -m venv .venv
    echo Then: .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
