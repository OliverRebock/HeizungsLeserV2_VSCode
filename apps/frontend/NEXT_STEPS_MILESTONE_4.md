# Nächste Schritte Meilenstein 4+ - Heizungsleser V2

Meilenstein 3 (Frontend-Basis) wurde erfolgreich umgesetzt. Das Frontend ist voll funktionsfähig und für zukünftige Erweiterungen vorbereitet.

## Geplante Features für Meilenstein 4+

### 1. Dashboard-Persistenz im Backend
- **Problem:** Aktuell werden Dashboard-Favoriten im `localStorage` gespeichert.
- **Lösung:** Erstellung von Backend-Endpunkten (`/api/v1/dashboards/`) zur Speicherung von Widgets, Layouts und ausgewählten Entitäten pro Benutzer/Gerät.
- **Frontend-Anpassung:** Umstellung der `useDashboard`-Logik von `localStorage` auf API-Hooks.

### 2. Reporting & PDF-Export
- **Ziel:** Heizungsbauer sollen PDF-Berichte über den Systemstatus und Verbräuche generieren können.
- **Backend:** Integration einer PDF-Library (z.B. WeasyPrint oder ReportLab).
- **Frontend:** Implementierung des Reporting-Tabs im Geräte-Detailbereich mit Zeitraumwahl und Template-Auswahl.

### 3. KI-basierte Analyse & Optimierung
- **Ziel:** Anomalieerkennung (z.B. Heizung taktet zu oft) und Effizienzberatung.
- **Frontend:** Visualisierung von KI-Insights als Warnungen oder Optimierungsvorschläge direkt in der Geräteübersicht.

### 4. Benutzerverwaltung für Kunden
- **Ziel:** `tenant_admin` soll weitere Benutzer (`tenant_user`) seines Unternehmens anlegen können.
- **Frontend:** Erweiterung des Admin-Bereichs um eine Benutzerliste pro Tenant.

### 5. Echtzeit-Updates (WebSockets)
- **Ziel:** Live-Werte ohne manuellen Refresh.
- **Backend:** FastAPI WebSockets für Event-Streaming.
- **Frontend:** Integration von `useSubscription` in die Geräte-Detailansicht.

### 6. i18n Internationalisierung
- **Ziel:** Unterstützung weiterer Sprachen (Englisch, Französisch, etc.).
- **Frontend:** Einführung von `react-i18next` und Auslagerung der deutschen Texte in JSON-Dateien.

### 7. PWA-Support
- **Ziel:** App-ähnliches Erlebnis auf dem Smartphone ohne App-Store-Installation.
- **Frontend:** Service-Worker und Web-Manifest Konfiguration für Vite.
