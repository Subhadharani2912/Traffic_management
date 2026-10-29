@echo off
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "backend\app.py"
) else (
    python "backend\app.py"
)