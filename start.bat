@echo off
cd /d "C:\Users\ec\Desktop\Pub"
echo === Mise a jour depuis GitHub ===
git pull
echo.
echo === Demarrage du serveur marketing ===
cd marketing_agent
python -m uvicorn webapp:app --host 0.0.0.0 --port 8000 --reload
pause
