@echo off
title ZenAquatique — Agent Marketing IA

set "APP_DIR=C:\Users\ec\Desktop\Pub\marketing_agent"

if not exist "%APP_DIR%" (
    color 4f
    echo.
    echo  ERREUR : dossier introuvable.
    echo  Chemin : %APP_DIR%
    echo.
    echo  Modifie la ligne APP_DIR dans ce fichier .bat
    echo.
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

cls
color 0b
echo.
echo  ============================================
echo    ZenAquatique  ^|  Agent Marketing IA
echo    http://localhost:8000
echo  ============================================
echo.
echo  Demarrage du serveur...
echo.

:: Ouvre le navigateur apres 3 secondes (sans bloquer)
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

:: Lance le serveur (logs visibles dans cette fenetre)
python webapp.py
pause
