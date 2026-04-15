# Go/No-Go One-Pager

Stand: 2026-04-15
Einsatz: Deployment-Call (Livegang)

## Ziel
In maximal 5 Minuten eine klare Go/No-Go-Entscheidung treffen.

## Rollen im Call
- Deployment Lead: moderiert und entscheidet final
- Ops Lead: Infrastruktur/Container/Monitoring
- QA/Fachtest: fachliche Kernprozesse

## Harte Go-Kriterien (muessen alle erfuellt sein)
- [ ] Backend Health ist stabil (HTTP 200)
- [ ] Frontend ist erreichbar (HTTP 200)
- [ ] Container-Zustand stabil (backend/frontend Up, db healthy)
- [ ] Letzter Smoke-Test erfolgreich
- [ ] Keine offenen kritischen Security-Befunde
- [ ] Rollback-Referenz (Commit/Tag/Image) dokumentiert
- [ ] DB-Snapshot vor Cutover bestaetigt

## No-Go-Trigger (ein Treffer reicht)
- [ ] Backend Health instabil oder rot
- [ ] Frontend nicht stabil erreichbar
- [ ] Kritische 5xx-Fehlerhaeufung in Logs/Monitoring
- [ ] Fachlich kritischer Defekt in Login/Dashboard/Device/Analyse
- [ ] Migration oder Datenkonsistenz nicht eindeutig korrekt

## 60-Sekunden Statusrunde (je Rolle)
Deployment Lead:
- Geplanter Scope unveraendert?
- Kommunikationsweg fuer Incident klar?

Ops Lead:
- Container/Infra stabil?
- Monitoring aktiv und beobachtet?

QA/Fachtest:
- Kernpfade geprueft?
- Ergebnis eindeutig freigabefaehig?

## Entscheidungsprotokoll
- Zeitpunkt Entscheidung:
- Ergebnis: GO / NO-GO
- Entscheider:
- Begruendung (1-2 Saetze):

## Sofortkommandos im Call
Compose Status:
`docker compose -f infra/docker-compose.yml ps`

Smoke-Test:
`pwsh -File LIVE/smoke/smoke_live.ps1 -WriteReport`

Backend Health:
`Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing`

Frontend Health:
`Invoke-WebRequest -Uri http://localhost:3001 -UseBasicParsing`

## Bei NO-GO
- Deployment stoppen
- Rollback gemaess `LIVE/ROLLBACK_RUNBOOK.md` starten
- Stakeholder-Update senden (Status + naechster Zeitslot)
