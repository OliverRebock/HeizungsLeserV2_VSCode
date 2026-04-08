@echo off
echo.
echo ============================================================
echo   Heizungsleser V2 - System Update (Docker)
echo ============================================================
echo.
echo Dieses Skript baut die Container neu und startet sie, 
echo damit alle Code-Aenderungen (z.B. Version v2.3.0) aktiv werden.
echo.

REM Pruefe ob wir im richtigen Verzeichnis sind
if not exist "infra\docker-compose.yml" (
    echo [FEHLER] Bitte starte das Skript aus dem Projekt-Hauptverzeichnis!
    exit /b 1
)

echo [1/3] Container stoppen...
docker-compose -f infra/docker-compose.yml down

echo.
echo [2/3] Neue Images bauen (dies kann einen Moment dauern)...
docker-compose -f infra/docker-compose.yml build --no-cache

echo.
echo [3/3] System neu starten...
docker-compose -f infra/docker-compose.yml up -d

echo.
echo ============================================================
echo   UPDATE ERFOLGREICH ABGESCHLOSSEN
echo ============================================================
echo.
echo Frontend: http://localhost:3001
echo Backend:  http://localhost:8000/docs
echo.
pause