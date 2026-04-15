# Live Ops Commands

## Wichtig: Produktionspfade
- App Stack auf Server: `/opt/heizungsleser-v2`
- NPM Stack auf Server: `/opt/npm`

## Compose Status
`docker compose -f infra/docker-compose.yml ps`

## Compose Logs
`docker compose -f infra/docker-compose.yml logs backend --tail 200`
`docker compose -f infra/docker-compose.yml logs frontend --tail 200`
`docker compose -f infra/docker-compose.yml logs db --tail 200`

## Health Checks
`Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing`
`Invoke-WebRequest -Uri http://localhost:3001 -UseBasicParsing`

## Smoke Test
`pwsh -File LIVE/smoke/smoke_live.ps1 -WriteReport`

## Security Checks
Python:
`c:/HeizungsleserV2 VS_Code/.venv/Scripts/python.exe -m pip_audit`

Frontend (im Container):
`docker compose -f infra/docker-compose.yml exec -T frontend npm audit --omit=dev --json`

## Produktions-Checks ueber Domain
Login-Token holen:
`curl -k -X POST https://heizungsleser.de/api/v1/auth/login -H "Content-Type: application/x-www-form-urlencoded" --data "username=admin@example.com&password=adminpass"`

Geschuetzter Endpoint (soll 401 ohne Token, 200 mit Token liefern):
`curl -k -i https://heizungsleser.de/api/v1/users/`

## NPM Proxy Validierung (auf Server)
Aktive Proxy-Datei pruefen:
`sed -n '1,140p' /opt/npm/data/nginx/proxy_host/1.conf`

Muss enthalten:
- Frontend Upstream: `heizungsleser-v2-frontend:80`
- API Upstream: `heizungsleser-v2-backend:8000`

NPM neu laden:
`cd /opt/npm && docker compose restart npm`

## DB Initialisierung (Pflicht bei frischer DB)
Migration:
`cd /opt/heizungsleser-v2 && docker compose exec backend sh -lc 'alembic upgrade head'`

Initial Admin:
`cd /opt/heizungsleser-v2 && docker compose exec backend sh -lc 'PYTHONPATH=/app python -m app.initial_data'`

## Data-Minimum (Tenant + Device)
Wenn Login geht, aber keine Geraete sichtbar sind:
1. Tenant anlegen (falls leer)
2. Device anlegen (tenant_id setzen, Bucket setzen)

Beispiel Device-Create:
`curl -k -X POST https://heizungsleser.de/api/v1/devices/ -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" --data '{"tenant_id":1,"display_name":"Heizungsanlage","source_type":"influxdb_v2","influx_database_name":"ha_Input_beyer1V2","is_active":true}'`
