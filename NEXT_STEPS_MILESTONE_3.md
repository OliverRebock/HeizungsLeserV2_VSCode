# Meilenstein 3 Vorbereitung (Frontend)

Dieses Dokument beschreibt die für das Frontend (Meilenstein 3) getroffenen Vorbereitungen im Backend.

## API-Ziele
Das Backend bietet eine saubere REST-API unter `/api/v1/`. Alle Endpunkte sind via Swagger unter `http://localhost:8000/docs` dokumentiert.

## Mandantenfähigkeit (Multi-Tenancy)
- Das Backend erzwingt Mandantentrennung auf API-Ebene.
- Benutzer sehen nur Daten (Devices, Entities, Timeseries) ihrer zugeordneten Tenants.
- `platform_admin` hat globalen Zugriff.

## Datenmodell für Diagramme
Die API-Antwort für Zeitreihen (`GET /api/v1/data/{deviceId}/timeseries`) ist speziell für den Vergleich mehrerer Entitäten in einem Chart optimiert:
- Einheitliches Punkt-Format (`ts`, `value`, `state`).
- Metadaten pro Serie (Domain, Data Kind, Friendly Name).
- Unterstützung für numerische, binäre und textuelle Daten.

## Vorbereitete Features
- **Geräte-Management:** Logische Abstraktion von physischen Influx-Datenbanken.
- **Auto-Provisionierung:** Automatische Generierung von Influx-DB-Namen nach dem Muster `ha_Input_{tenant}{index}`.
- **CORS:** Bereit für den Zugriff aus einem separaten Frontend-Container.
- **Auth:** JWT-basiert mit Rollenprüfung (RBAC).

## Nächste Schritte für das Frontend
1. **API-Client:** Generierung eines TypeScript-Clients aus der OpenAPI-Spezifikation.
2. **Dashboard-Engine:** Visualisierung der Zeitreihen mit Bibliotheken wie Recharts, Chart.js oder Apache ECharts.
3. **Geräte-Auswahl:** UI zur Auswahl zwischen HA1, HA2 etc. pro Mandant.
4. **Vergleichs-Modus:** UI-Komponente, um mehrere `entity_ids` an den Timeseries-Endpunkt zu senden.
