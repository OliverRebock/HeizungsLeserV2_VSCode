# Übergabeprotokoll Heizungsleser V2 - Stand 30.03.2026 (Abend)

## 🚀 Status Quo
Die Anwendung wurde erfolgreich von InfluxDB 3 auf **InfluxDB 2** migriert und für den Produktivbetrieb mit mehreren Mandanten (Kunden) vorbereitet. Alle Systeme laufen stabil unter **http://localhost:3001**.

## ✅ Erledigte Meilensteine heute:

### 1. InfluxDB 2 Migration & Datenmuster
*   Komplette Umstellung des Backends auf native **Flux-Queries**.
*   Intelligente Entitätserkennung: Das System findet nun alle ~90 Entitäten im Bucket `ha_Input_beyer1V2`.
*   **Namensbereinigung:** Geräte-Präfixe (ems-esp, ebusd) werden automatisch entfernt. Deutsche Klarnamen werden bevorzugt.

### 2. Dynamischer Geräte-Status (5-Minuten-Regel)
*   Die statische "Aktiv"-Anzeige wurde durch eine **Live-Statusprüfung** ersetzt.
*   Ein Gerät wird nur als **Online** markiert, wenn in den letzten 5 Minuten Daten in InfluxDB eingegangen sind.
*   Anzeige von **"Zuletzt gesehen"** in der Kundenverwaltung und auf der Detailseite.

### 3. Kundenverwaltung & Influx-Automatisierung
*   **Auto-Provisioning:** Beim Anlegen eines Geräts wird nun vollautomatisch ein InfluxDB-Bucket und ein exklusiver Auth-Token generiert.
*   **Custom Buckets:** Der Bucket-Name kann beim Anlegen frei gewählt werden (Vorschlag: `ha_Input_kundenname`).
*   **Löschfunktion:** Kunden und Geräte können nun sauber über die GUI gelöscht werden.

### 4. Visualisierung & Usability
*   **Select-Werte:** Betriebsmodi und Zustände (Text) werden nun als State-Timeline visualisiert.
*   **Binary-Sensoren:** Anzeige von **"An/Aus"** statt 0/1 in allen Diagrammen und Tooltips.
*   **UI-Optimierung:** Tabellenspalten verbreitert, volle Namen sichtbar.

### 5. Technisches Anti-Cache Setup
*   **Vite Cache-Busting:** Jeder Build generiert nun Zeitstempel-basierte Dateinamen.
*   **Nginx Security:** Radikale `no-store` Header verhindern veraltete Browser-Ansichten auf Port 3001.

---

## 📝 Plan für morgen / Nächste Schritte:

1.  **Multi-Geräte Test:** Validierung, ob Daten von zwei verschiedenen HomeAssistant-Instanzen (verschiedene Tokens/Buckets) gleichzeitig sauber getrennt im Dashboard erscheinen.
2.  **Dashboard-Persistenz:** Prüfung, ob die vom User angelegten Widgets dauerhaft gespeichert bleiben.
3.  **Fehler-Reporting:** Optionale Benachrichtigung, wenn ein Gerät länger als X Stunden offline ist.
4.  **Daten-Export:** Implementierung eines CSV/Excel-Exports für die gefilterten Zeitreihen.

**Schönen Feierabend! Das System ist in einem sehr sauberen Zustand.**
