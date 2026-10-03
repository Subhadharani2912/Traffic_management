@echo off
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" "backend\app.py"