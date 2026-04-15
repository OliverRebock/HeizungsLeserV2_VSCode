# Go/No-Go Moderator-Skript (90 Sekunden)

Stand: 2026-04-15

## Start (10s)
"Wir machen jetzt die finale Go/No-Go-Entscheidung fuer den Livegang. Ziel: klare Entscheidung in 90 Sekunden."

## Rollen-Check (15s)
"Deployment Lead, Ops Lead und QA/Fachtest bitte jeweils nur den aktuellen Status in einem Satz."

## Harte Go-Kriterien (35s)
"Ich lese die Pflichtpunkte vor. Bitte nur mit Ja/Nein antworten."
- Backend Health stabil 200?
- Frontend stabil 200?
- Container stabil: backend/frontend Up, db healthy?
- Letzter Smoke-Test erfolgreich?
- Keine offenen kritischen Security-Befunde?
- Rollback-Referenz dokumentiert?
- DB-Snapshot bestaetigt?

"Wenn ein Punkt Nein ist, ist es automatisch No-Go."

## No-Go-Trigger (15s)
"Liegt eines davon vor?"
- Instabile Health-Checks
- Kritische 5xx-Fehlerhaeufung
- Fachlich kritischer Defekt in Kernpfaden
- Daten-/Migrationsproblem

"Wenn Ja: No-Go und Rollback-Runbook."

## Entscheidung (15s)
"Finale Entscheidung: Go oder No-Go?"
- Wenn Go: "Go ist erteilt. Cutover gemaess LIVE/CUTOVER_PLAN.md starten."
- Wenn No-Go: "No-Go. Rollback gemaess LIVE/ROLLBACK_RUNBOOK.md jetzt starten."

## Protokoll (Post-Call, 10s)
- Zeitpunkt:
- Ergebnis: Go/No-Go
- Entscheider:
- Begruendung (1 Satz)

## Optional: Sofortkommandos
Compose Status:
`docker compose -f infra/docker-compose.yml ps`

Smoke-Test:
`pwsh -File LIVE/smoke/smoke_live.ps1 -WriteReport`
