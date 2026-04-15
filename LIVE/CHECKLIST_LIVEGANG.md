# Go-Live Checkliste

## 1. Freeze und Vorbereitung
- [ ] Deployment-Zeitfenster festgelegt und kommuniziert
- [ ] Verantwortliche benannt (Deployment, Monitoring, Fallback)
- [ ] Letztes Backup/DB-Snapshot erstellt
- [ ] Aktueller Commit/Tag fuer Rollback dokumentiert

## 2. Sicherheits- und Abhaengigkeitsstatus
- [ ] Python Audit ohne offene kritische Luecken
- [ ] Frontend Production Audit ohne offene kritische Luecken
- [ ] Verwendete Abhaengigkeitsstaende in `LIVE/artifacts/` abgelegt

## 3. Infrastruktur und Konfiguration
- [ ] Produktions-Umgebungsvariablen geprueft (Secrets, URLs, CORS)
- [ ] Datenbank-Connectivity und Migrationspfad geprueft
- [ ] Ports/Firewall/Reverse-Proxy Regeln geprueft
- [ ] NPM/Reverse-Proxy Zielhost geprueft (Frontend: `heizungsleser-v2-frontend:80`)
- [ ] NPM Custom Location `/api` geprueft (Backend: `heizungsleser-v2-backend:8000`)
- [ ] NPM SSL-Host aktiv und Zertifikat gueltig

## 4. Datenbank-Initialisierung (Pflicht vor erstem Login)
- [ ] Alembic Migration ausgefuehrt: `alembic upgrade head`
- [ ] Initial-Admin angelegt: `PYTHONPATH=/app python -m app.initial_data`
- [ ] DB-Minimum geprueft (mind. 1 Tenant, mind. 1 Device)

## 5. Pre-Live Validierung
- [ ] `pwsh -File LIVE/smoke/smoke_live.ps1` erfolgreich
- [ ] Backend Health Endpoint liefert HTTP 200
- [ ] Frontend liefert HTTP 200
- [ ] Kernpfade im UI getestet (Login, Dashboard, Device-Detail, Analyse)
- [ ] API Login liefert Token: `POST /api/v1/auth/login`
- [ ] Authentifizierter API-Test erfolgreich (z. B. `GET /api/v1/users/` != 502)
- [ ] Device-Liste liefert keine Leerantwort durch Initialisierungsfehler

## 6. Go-Live Ausfuehrung
- [ ] Release ausgerollt
- [ ] Container/Pods in gesundem Status
- [ ] Erste 10-15 Minuten engmaschig beobachten (Logs, Error Rate, Latenz)

## 7. Post-Live Abnahme
- [ ] Smoke-Test erneut erfolgreich
- [ ] Monitoring ohne auffaellige Fehler
- [ ] Fachliche Stichprobe mit echten Nutzungsfaellen erfolgreich
- [ ] Go-Live Abnahme dokumentiert

## 8. Rollback-Plan (wenn noetig)
- [ ] Trigger-Kriterien klar (z. B. Health rot, hohe 5xx-Rate)
- [ ] Rollback auf letzten stabilen Stand durchfuehrbar
- [ ] Nach Rollback Smoke-Test erfolgreich
