@echo off
cd /d "%~dp0"
echo Demarrage de l'assistant email...
start "" python app.py
timeout /t 2 /nobreak >nul
start "" ngrok http 5000
timeout /t 3 /nobreak >nul
start http://localhost:5000
echo.
echo L'URL publique (mobile) est visible dans la fenetre ngrok.
