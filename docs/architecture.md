# Heizungsleser V2 - Architektur-Dokumentation

## Projekt-Überblick
Multi-Mandanten-Webanwendung für Heizungsbauer zur Visualisierung von Heizungsdaten aus Home Assistant (InfluxDB 3).

## Domänenmodell
- **Tenant (Mandant):** Ein Kunde (z. B. Firma Beyer).
- **User:** Ein Benutzer, der einem oder mehreren Tenants zugeordnet ist (RBAC).
- **Device:** Ein logisches Home-Assistant-Gerät (HA1, HA2 etc.).
- **DataSource:** Die physische Anbindung an InfluxDB (kapselt Datenbanknamen und Retention).

## Rollenmodell (RBAC)
1. **platform_admin:** Voller Zugriff auf alle Tenants, User und Devices.
2. **tenant_admin:** Verwaltung des eigenen Tenants (Benutzer, Devices).
3. **tenant_user:** Nur Lesezugriff auf Devices des eigenen Tenants.

## Influx-Adapter-Konzept
Da InfluxDB 3 verschiedene Schemata liefern kann, nutzt das Backend **Schema-Introspektion**.
Der Adapter ermittelt:
- Welche Messungen (Tables) vorhanden sind.
- Welche Felder numerisch (plottbar) oder textuell (Status) sind.
- Normalisierung in ein einheitliches API-Format für das Frontend.

## API-Ziele
- Klare Trennung zwischen Admin- und User-Endpunkten.
- Bereitstellung von normalisierten Zeitreihen-Daten für Diagramme.
- Vorbereitung für Dashboards und PDF-Reporting.

## Vorbereitung Meilenstein 3 (Frontend)
- **OpenAPI:** Vollständige Dokumentation aller Endpunkte.
- **DTOs:** Stabile Datenstrukturen für die UI.
- **CORS:** Konfiguriert für Web-Zugriff.
