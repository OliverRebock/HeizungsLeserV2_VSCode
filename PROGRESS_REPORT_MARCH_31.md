# Fortschrittsbericht - 31. März 2026 (Feierabend-Update)

## Erreichte Meilensteine Heute

### 1. Zuverlässiger Live-Status & InfluxDB-Optimierung
*   **Fix für Schema-Konflikte:** Das Backend ignoriert nun Datentyp-Fehler (Float/String) bei der Zeitstempel-Ermittlung. Der Online-Status ist nun für alle Geräte (auch HA1 Beyer) präzise.
*   **Bucket-Management:** Mehrere Buckets (`ha_Input_beyer1V2`, `ha_Input_rebock`) wurden tiefengereinigt (Löschung + Neuerstellung), um "Leichen" im Index zu entfernen.
*   **Einheiten-Erkennung:** Das System erkennt nun automatisch Einheiten wie `°C`, `W`, `kW`, `kWh` direkt aus den InfluxDB-Metadaten und zeigt diese in Diagrammen und Kacheln an.

### 2. Dashboard-Persistenz & Interaktivität
*   **Backend-Speicherung:** Dashboard-Widgets werden nun in der PostgreSQL-Datenbank gespeichert (statt LocalStorage).
*   **Interaktive Widgets:** Ein Klick auf ein Dashboard-Widget öffnet nun direkt das Detail-Modal mit dem Graphen.
*   **Usability:** Modalfenster lassen sich nun mit der `Esc`-Taste schließen.

### 3. Sicherheit & Admin-Funktionen
*   **IDOR-Schutz:** Zugriff auf Gerätedaten wird nun strikt auf den jeweiligen Mandanten (Tenant) geprüft.
*   **Token-Sicherheit:** InfluxDB-Tokens werden standardmäßig maskiert. Administratoren können den vollen Token nun sicher in der **Kundenverwaltung** über die Schaltfläche `[VOLL ANZEIGEN]` abrufen.
*   **CORS-Härtung:** Zugriff auf die API wurde auf bekannte Domains beschränkt (localhost:3000, 3001, 5173).

### 4. UI/UX Verbesserungen
*   **Responsive Design:** Optimierung der Abstände und Layouts für mobile Endgeräte.
*   **Tab-Reihenfolge:** Die Navigation in der Detailansicht wurde logisch neu sortiert (1. Übersicht, 2. Dashboard, 3. Entitäten, 4. Verläufe).
*   **Versions-Tracking:** Einführung einer sichtbaren Versionsnummer (`v2.0.14-esc-support`) zur Vermeidung von Browser-Cache-Problemen.

## Bereinigung
*   Alle temporären Test-Skripte (`check_*.py`, `diagnose_*.py`, etc.) und CSV-Exporte wurden vom Server entfernt.
*   Die Docker-Umgebung wurde vollständig neu gebaut und ist auf dem Stand `v2.0.14-esc-support`.

**Schönen Feierabend! Wir machen morgen an den nächsten Punkten (z.B. Benachrichtigungs-Logik oder Export-Button) weiter.**
