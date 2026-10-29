@echo off
cd /d "%~dp0"
echo Starting Traffic Management System Backend and Frontend...
start "Traffic Backend" cmd /k "call start_backend.bat"
start "Traffic Frontend" cmd /k "call start_frontend.bat"
echo Services launched.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
