# Heizungsleser V2

## Beschreibung
Multi-Mandanten-Backend für die Visualisierung von Heizungsdaten aus Home Assistant (InfluxDB 3).

## Projektstruktur
- `apps/backend`: FastAPI Backend.
- `apps/frontend`: Placeholder für das zukünftige Frontend (React/Vue).
- `infra`: Docker-Compose und Infrastruktur-Files.
- `docs`: Dokumentation und ADRs.

## Benutzerverwaltung und Rollenmodell

Heizungsleser V2 nutzt ein mandantenfähiges Rollenmodell (RBAC):

### Rollen
- **Platform Admin (`platform_admin` / Superuser)**:
  - Voller Zugriff auf alle Mandanten.
  - Kann Mandanten anlegen/bearbeiten.
  - Kann Geräte anlegen (exklusives Recht).
  - Kann Benutzer für beliebige Mandanten anlegen, bearbeiten und löschen.
  - Kann Passwörter aller Benutzer zurücksetzen.
- **Tenant Admin (`tenant_admin`)**:
  - Zugriff nur auf den eigenen Mandanten.
  - Kann Benutzer für den eigenen Mandanten anlegen, bearbeiten und löschen.
  - Kann Passwörter der Benutzer im eigenen Mandanten zurücksetzen.
  - Kann KEINE Geräte anlegen.
  - Kann KEINE Mandanten anlegen.
- **Tenant User (`tenant_user`)**:
  - Kann nur Daten des eigenen Mandanten sehen und Funktionen nutzen.
  - Kein Zugriff auf die Benutzerverwaltung.

### API-Endpunkte (Benutzer)
- `GET /api/v1/users/` - Liste der Benutzer (Gescoped nach Rolle).
- `POST /api/v1/users/` - Benutzer anlegen.
- `GET /api/v1/users/{user_id}` - Benutzerdetails.
- `PUT /api/v1/users/{user_id}` - Benutzer aktualisieren.
- `DELETE /api/v1/users/{user_id}` - Benutzer löschen.
- `POST /api/v1/users/{user_id}/reset-password` - Passwort direkt durch Admin setzen.

## Starten (Lokal)
1. `.env.example` kopieren: `cp .env.example .env`
2. Docker-Container starten: `docker compose up -d`
3. Backend ist erreichbar unter: `http://localhost:8000/docs`

## Voraussetzungen
- Docker Desktop
- Python 3.12 (für lokale Entwicklung ohne Docker)
