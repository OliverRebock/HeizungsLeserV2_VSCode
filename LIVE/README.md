# LIVE Ordner

Dieser Ordner enthaelt eine getrennte Go-Live-Mappe.
Die laufende DEV-Umgebung bleibt unveraendert.

## Inhalt
- `CHECKLIST_LIVEGANG.md`: Konkrete Release- und Rollback-Checkliste
- `PREFLIGHT_10_MIN.md`: Kompakter 10-Minuten-Preflight mit Go/No-Go Gates
- `GO_NO_GO_ONE_PAGER.md`: Kompakte Entscheidungsgrundlage fuer den Deployment-Call
- `GO_NO_GO_MODERATOR_SCRIPT.md`: 90-Sekunden-Skript zum direkten Vorlesen im Call
- `CUTOVER_PLAN.md`: Zeitgesteuerter Ablaufplan (T-30 bis T+30)
- `ROLLBACK_RUNBOOK.md`: Operatives Rollback-Vorgehen
- `COMMANDS.md`: Wichtige Live-Ops-Kommandos
- `smoke/smoke_live.ps1`: Automatischer Smoke-Test vor/nach Go-Live
- `artifacts/`: Kopien der aktuell relevanten Abhaengigkeits- und Compose-Dateien
- `reports/`: Ausgabe vergangener Smoke-Tests

## Schnellstart
1. Smoke-Test lokal ausfuehren:
   `pwsh -File LIVE/smoke/smoke_live.ps1`
2. Checkliste durcharbeiten:
   `LIVE/CHECKLIST_LIVEGANG.md`

## Lessons Learned aus letztem Livegang
- Reverse-Proxy (NPM) nie nur auf Datei-Ebene patchen, sondern immer aktiv im NPM-Host verifizieren.
- Vor Go-Live immer Public-Login (`/api/v1/auth/login`) end-to-end testen.
- Frische DB braucht zwingend: Migration, Initial-Admin, mindestens einen Tenant und ein Device.
- Wenn Login geht aber keine Geraete sichtbar sind, zuerst Tenant/Device-Basisdaten pruefen.

Hinweis: Alle Dateien in `artifacts/` sind Kopien als Live-Referenzstand.
