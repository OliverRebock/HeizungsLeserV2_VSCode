# Cutover Plan (T-30 bis T+30)

## Rollen
- Deployment Lead: steuert den Ablauf und entscheidet Go/No-Go
- Ops Lead: Infrastruktur, Container, Monitoring, Logs
- QA/Fachtest: fachliche Kernfluesse und Freigabe

## Voraussetzungen
- Letzter Smoke-Test aus `LIVE/smoke/smoke_live.ps1` war erfolgreich
- Backup/DB-Snapshot kurz vor Cutover moeglich
- Rollback-Referenz (Commit/Tag/Image) dokumentiert

## T-30 Minuten
- [ ] Change-Freeze aktivieren (keine weiteren Code-Aenderungen)
- [ ] Team-Call oeffnen, Verantwortlichkeiten bestaetigen
- [ ] Monitoring-Dashboards oeffnen (API errors, latency, container health)
- [ ] Backup/DB-Snapshot vorbereiten

## T-20 Minuten
- [ ] Finale ENV/Secrets validieren (Prod-Werte)
- [ ] DNS/Proxy/TLS Routing pruefen
- [ ] Rollback-Kommandos griffbereit machen
- [ ] NPM Zielrouting hart pruefen (`frontend -> heizungsleser-v2-frontend:80`, `/api -> heizungsleser-v2-backend:8000`)
- [ ] Public Login-Request gegen Domain pruefen (`POST /api/v1/auth/login`)

## T-10 Minuten
- [ ] DB-Snapshot erstellen und Erfolg bestaetigen
- [ ] Letzten Pre-Cutover Smoke-Test laufen lassen
- [ ] Bei frischer DB: Migration + Initial-Admin + mindestens 1 Tenant + mindestens 1 Device sicherstellen
- [ ] Go/No-Go Entscheidung dokumentieren

## T-0 (Cutover)
- [ ] Deployment starten
- [ ] Container/Services auf "up/healthy" bestaetigen
- [ ] Backend Health Endpoint pruefen (HTTP 200)
- [ ] Frontend Endpoint pruefen (HTTP 200)

## T+10 Minuten
- [ ] Technischer Smoke-Test erneut ausfuehren
- [ ] Logs auf 4xx/5xx-Spikes pruefen
- [ ] CPU/RAM/Restart-Raten pruefen

## T+20 Minuten
- [ ] Fachliche Kernpfade testen:
  - [ ] Login
  - [ ] Dashboard
  - [ ] Device Detail
  - [ ] Analyse-Flow
- [ ] Device-Liste validieren (nicht leer aufgrund fehlender Initialdaten)
- [ ] Erste Anwenderfreigabe einholen

## T+30 Minuten
- [ ] Go-Live erfolgreich dokumentieren
- [ ] Hypercare-Fenster (z. B. 24h) bestaetigen
- [ ] Abschlussmeldung an Stakeholder senden

## No-Go / Sofort-Rollback Trigger
- Backend Health dauerhaft != 200
- Frontend nicht erreichbar
- Kritische Fehlerhaeufung (z. B. starke 5xx-Rate)
- Datenkonsistenz-/Migrationsproblem
- Login-Flow gegen Public Domain liefert 5xx
- API ueber Reverse Proxy zeigt falsche Upstreams (z. B. alte Hostnamen/Ports)
