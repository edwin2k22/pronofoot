@echo off
REM ════════════════════════════════════════════════════════════════════
REM  PronoFoot — lancement Windows (live auto + serveur web)
REM  Equivalent de start.sh pour Windows
REM  Usage : start.bat [poll_secondes] [port]
REM          start.bat 30 8077    (defaut)
REM          start.bat 20 8080    (poll 20s, port 8080)
REM ════════════════════════════════════════════════════════════════════
setlocal enabledelayedexpansion

REM ── Encodage UTF-8 pour les emojis et caracteres speciaux Python ────────
SET PYTHONIOENCODING=utf-8
SET PYTHONUTF8=1
chcp 65001 >nul 2>&1

SET LIVE_POLL=%1
IF "%LIVE_POLL%"=="" SET LIVE_POLL=30

SET PORT=%2
IF "%PORT%"=="" SET PORT=8077

echo.
echo  PronoFoot — demarrage intelligent (Windows)
echo    * Scheduler live : s'active a chaque coup d'envoi (poll %LIVE_POLL%s en match)
echo    * App web        : http://localhost:%PORT%/index.html
echo    * Fermez cette fenetre pour tout arreter
echo.

REM 0) Refresh complet au demarrage
echo  Initialisation (refresh complet)...
python -m collector.refresh
IF ERRORLEVEL 1 (
    echo  ERREUR lors du refresh initial. Verifiez votre connexion internet.
    echo  Le serveur va quand meme demarrer avec les donnees existantes.
)
echo.
echo  Pret.
echo.

REM 1) Demarrer le scheduler live en arriere-plan
echo  Demarrage du scheduler live...
start "PronoFoot-Live" /MIN cmd /c "SET PYTHONIOENCODING=utf-8&SET PYTHONUTF8=1&python -m collector.smart_live --live-poll %LIVE_POLL%"

REM 2) Demarrer le serveur web (bloquant — fermer la fenetre = tout arrete)
echo  Demarrage du serveur web sur le port %PORT%...
echo  Ouvrez votre navigateur sur : http://localhost:%PORT%/index.html
echo.
echo  Appuyez sur Ctrl+C pour arreter le serveur.
echo.
python -m collector.server %PORT%

REM Nettoyage : tuer le scheduler live quand le serveur s'arrete
taskkill /FI "WINDOWTITLE eq PronoFoot-Live" /F >nul 2>&1
echo.
echo  PronoFoot arrete.
