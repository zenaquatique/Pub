@echo off
cd /d "%~dp0"
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%
echo.
echo  ================================
echo   Assistant Email
echo   PC    : http://localhost:5000
echo   Mobile: http://%IP%:5000
echo  ================================
echo.
start "" python app.py
timeout /t 2 /nobreak >nul
start http://localhost:5000
