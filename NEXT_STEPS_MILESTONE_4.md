### Meilenstein 4: Erweiterte Features & Reporting

Nachdem Meilenstein 3 (Frontend-MVP) erfolgreich abgeschlossen wurde, sind dies die nächsten Schritte:

1. **Dashboard-Persistenz**
   - Implementierung der Backend-Endpunkte zum Speichern von Benutzer-Dashboards.
   - Umstellung des Frontends von `localStorage` auf API-basierte Persistenz.

2. **KI-Auswertung (Vorbereitung)**
   - Integration eines Services zur Analyse von Heizkurven.
   - UI-Komponenten zur Anzeige von KI-Empfehlungen.

3. **Reporting & PDF-Export**
   - Generierung von PDF-Berichten für Kunden.
   - Auswahl von Zeiträumen und Entitäten für den Export.

4. **Benutzerverwaltung für Mandanten**
   - `tenant_admin` kann weitere `tenant_user` anlegen.
   - Einladungs-System via E-Mail.

5. **Optimierung der Datenvisualisierung**
   - Unterstützung für Enum- und String-Zustände in den Charts (vorerst als separate Zeitleiste oder Status-Balken).
   - Erweiterte Filter für Zeiträume (Custom Date Range Picker).
   - Auto-Refresh Option für Live-Daten.
   - Implementierung von Server-side Aggregation/Downsampling bei großen Zeiträumen (z.B. 30d), um Frontend-Performance zu sichern.

6. **Reporting & PDF-Architektur**
   - Die aktuelle `DeviceDataResponse` Struktur ist bereits so ausgelegt, dass sie für PDF-Reports (z.B. via `playwright` oder `reportlab` im Backend) direkt wiederverwendet werden kann.
   - Trennung von Chart-Generierung (Frontend) und Daten-Aggregation (Backend) ermöglicht konsistente Berichte.
