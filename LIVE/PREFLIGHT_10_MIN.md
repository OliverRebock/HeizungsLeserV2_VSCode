# Preflight in 10 Minuten (One-Page)

Ziel: In 10 Minuten belastbar entscheiden, ob der Livegang gestartet werden darf.

## Minute 0-2: Container und Health
- [ ] Produktions-Stack laeuft (backend, frontend, db, npm)
- [ ] Backend Health ist gruen
- [ ] Frontend antwortet

Beispiel:
```powershell
ssh -i "C:\Users\reboc\.ssh\copilot_heizungsleser_ed25519" root@10.8.0.1 "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'npm|heizungsleser-v2'"
curl -k -i https://heizungsleser.de/login
```

## Minute 2-4: Reverse Proxy (NPM)
- [ ] Proxy Host zeigt auf Frontend: heizungsleser-v2-frontend:80
- [ ] Custom Location /api zeigt auf Backend: heizungsleser-v2-backend:8000
- [ ] SSL aktiv, Domain-Zertifikat gueltig, Force SSL aktiv

No-Go wenn:
- [ ] Alte Ziele sichtbar (z. B. heizungsleser-frontend oder Port 8001)

## Minute 4-6: Auth End-to-End
- [ ] Public Login liefert Token
- [ ] Geschuetzter Endpoint liefert mit Token erfolgreich

Beispiel:
```powershell
$login = curl.exe -k -s -X POST https://heizungsleser.de/api/v1/auth/login -H "Content-Type: application/x-www-form-urlencoded" --data "username=admin@example.com&password=adminpass"
$token = ($login | ConvertFrom-Json).access_token
curl.exe -k -i https://heizungsleser.de/api/v1/users/ -H "Authorization: Bearer $token"
```

## Minute 6-8: Daten-Basis vorhanden
- [ ] Mindestens 1 Tenant vorhanden
- [ ] Mindestens 1 Device vorhanden
- [ ] Device-Liste ist nicht leer

Beispiel:
```powershell
curl.exe -k -i https://heizungsleser.de/api/v1/devices/ -H "Authorization: Bearer $token"
```

No-Go wenn:
- [ ] Login funktioniert, aber Device-Liste bleibt leer ([])

## Minute 8-10: Go/No-Go Entscheidung
Go nur wenn alle Gates gruen sind:
1. Infrastruktur/Health
2. NPM Routing
3. Login und API Auth
4. Tenant + Device Basisdaten

## Schnell-Fix bei frischer DB
Wenn Login oder Device-Liste wegen Initialzustand fehlschlaegt:
1. Migration ausfuehren: alembic upgrade head
2. Initial-Admin anlegen: PYTHONPATH=/app python -m app.initial_data
3. Tenant + Device anlegen

## Abschlussprotokoll (2 Zeilen)
- Entscheidung: GO oder NO-GO
- Grund / Befunde: (z. B. "GO - alle 4 Gates gruen")
