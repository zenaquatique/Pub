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
echo  ============================================
echo.

:: ── Tunnel Cloudflare (acces depuis n'importe ou) ────────────────────────
where cloudflared >nul 2>&1
if %errorlevel%==0 (
    echo  Lancement du tunnel Cloudflare...
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:8000"
    echo  L'URL publique s'affiche dans la fenetre [Cloudflare Tunnel].
) else (
    echo  [!] cloudflared non installe.
    echo      Pour acceder depuis un autre reseau, installe-le :
    echo      winget install Cloudflare.cloudflared
    echo.
    echo  Acces local uniquement : http://localhost:8000
)

echo.
echo  Demarrage du serveur...
echo.

:: Ouvre le navigateur apres 3 secondes (sans bloquer)
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

:: Lance le serveur (logs visibles dans cette fenetre)
python webapp.py
pause
