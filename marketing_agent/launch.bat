@echo off
cd /d "%~dp0"
echo.
echo ================================
echo   Agent Marketing IA
echo   http://localhost:8000
echo ================================
echo.
start "" "http://localhost:8000"
python webapp.py
pause
