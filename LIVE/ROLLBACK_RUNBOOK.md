# Rollback Runbook

## Ziel
Schnelle Rueckkehr auf den letzten stabilen Stand bei kritischem Verhalten nach Cutover.

## Trigger (mindestens einer)
- Backend Health rot oder instabil
- Frontend nicht stabil erreichbar
- Kritische Fehler in Logs/Monitoring
- Fachlich kritischer Defekt in Kernprozess

## Vorbereitung
- Letzte stabile Referenz dokumentieren:
  - Commit/Tag:
  - Docker Image(s):
  - DB Snapshot ID:
- Verantwortliche:
  - Entscheidung: Deployment Lead
  - Umsetzung: Ops Lead
  - Verifikation: QA/Fachtest

## Rollback Schritte
1. Incident ansagen und Rollback-Entscheidung festhalten
2. Aktuelles fehlerhaftes Deployment stoppen
3. Letzte stabile Version deployen
4. Falls noetig DB auf Snapshot zuruecksetzen (nur wenn fachlich notwendig und freigegeben)
5. Services auf gesunden Status pruefen
6. Smoke-Test ausfuehren: `LIVE/smoke/smoke_live.ps1 -WriteReport`
7. Fachlichen Kurztest ausfuehren (Login, Dashboard, Device Detail, Analyse)
8. Stakeholder informieren (Status: stabil auf Vorversion)

## Nachbereitung
- Ursache protokollieren
- Action Items und Fix-Plan erfassen
- Neuer Go-Live-Termin erst nach Nachweis der Korrektur
