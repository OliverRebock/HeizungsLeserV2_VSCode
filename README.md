# Heizungsleser V2 – Intelligente Heizungsüberwachung & Analyse (v2.3.3)

Heizungsleser V2 ist eine hochmoderne, mandantenfähige Plattform zur **Echtzeit-Überwachung**, **technischen Diagnose** und **KI-gestützten Optimierung** von Heizungssystemen (insbesondere Wärmepumpen). Die Anwendung schließt die Lücke zwischen komplexen Rohdaten aus Smart-Home-Systemen (wie Home Assistant) und verständlichen, handlungsorientierten Analysen für Fachbetriebe und Endkunden.

---

## 🌟 Warum Heizungsleser V2? (Vorteile)

*   **Effizienzsteigerung:** Identifizieren Sie unnötiges Takten und suboptimale Heizkurven, bevor sie zu hohen Stromrechnungen führen.
*   **KI-Expertise auf Knopfdruck:** Nutzen Sie die Power von OpenAI (GPT-4o), um komplexe Temperaturverläufe wie ein erfahrener Heizungstechniker interpretieren zu lassen.
*   **Mandantensicherheit (Multi-Tenancy):** Entwickelt für Dienstleister. Verwalten Sie hunderte Kunden in einer einzigen Oberfläche bei strikter Datentrennung.
*   **Herstellerunabhängig:** Durch die Anbindung an InfluxDB werden Daten verschiedenster Hersteller (Viessmann, Vaillant, Wolf, Buderus etc.) einheitlich verarbeitet.
*   **Zukunftssicher:** Modernster Tech-Stack (FastAPI, React, InfluxDB 2), der auf Performance und Skalierbarkeit ausgelegt ist.

---

## 🚀 Kernfunktionen im Detail

### 1. Rollenbasierte Benutzerverwaltung (RBAC)
Das System bildet die reale Hierarchie von Service-Strukturen ab:
*   **Plattform-Admin (platform_admin):** Globaler Vollzugriff. Darf Mandanten, Geräte und alle Benutzerrollen (inkl. Admins) verwalten. Nur der Plattform-Admin kann Geräte anlegen oder bearbeiten.
*   **Mandanten-Admin (tenant_admin):** Eingeschränkte Verwaltung innerhalb des eigenen Mandanten. Darf nur `tenant_user` anlegen, bearbeiten oder löschen. Hat **keinen** Zugriff auf die Gerätekonfiguration oder mandantenübergreifende Daten.
*   **Endbenutzer (tenant_user):** Reiner Lesezugriff auf Dashboards und Analysen der zugeordneten Heizungssysteme innerhalb seines Mandanten.
*   **Sicherheit:** Ein striktes Scoping auf Mandantenebene (Multi-Tenancy) verhindert unbefugten Datenzugriff. Die Rollenhierarchie ist im Backend durch Policies abgesichert.

### 2. Echtzeit-Monitoring & Dashboard
Verwandeln Sie Datenfriedhöfe in Erkenntnisse:
*   **Live-Metriken:** Vorlauf-, Rücklauf- und Außentemperaturen werden in Echtzeit visualisiert.
*   **Geräte-Zustand:** Sofortige Übersicht über den Online-Status und die Aktivität aller registrierten Instanzen.
*   **Interaktive Charts:** Analyse von Zeitreihendaten zur Optimierung von Schaltzyklen und Modulationsgraden.

### 3. KI-Analyse & Deep Analysis
Das Herzstück der Anwendung basiert auf OpenAI GPT-4o:
*   **KI-Analyse (Zusammenfassung):** Generiert auf Knopfdruck einen verständlichen Bericht über den aktuellen Betriebszustand basierend auf den Zeitreihendaten der letzten Stunden/Tage.
*   **Deep Analysis (Technische Diagnose):** Eine vertiefte Analyse, die spezifische Anomalien identifiziert, Effizienzwerte bewertet und konkrete Optimierungsvorschläge (z. B. Anpassung der Heizkurve) liefert.
*   **Mustererkennung:** Die KI erkennt ineffizientes Verhalten wie "Taktung" oder "Pendeln", das in reinen Tabellen oft übersehen wird.

### 4. Kunden- & Geräteverwaltung
Professionelles Management für Fachbetriebe:
*   **Mandanten-Logik:** Jedes Gerät (Wärmepumpe/Heizung) ist eindeutig einem Mandanten zugeordnet.
*   **InfluxDB 2 Integration:** Jedes Gerät nutzt spezifische InfluxDB-Parameter (Bucket, Token, URL) für eine flexible Datenanbindung.

---

## 🛠️ Technologie-Stack

| Komponente | Technologie | Beschreibung |
| :--- | :--- | :--- |
| **Backend** | Python 3.12 / FastAPI | Hochperformante, asynchrone API-Verarbeitung. |
| **Datenbank (Meta)** | PostgreSQL | Verwaltung von Benutzern, Rollen und Mandantenstrukturen. |
| **Datenbank (Time)** | InfluxDB 2.x | Optimiert für Zeitreihendaten (aktuelle Zielplattform). |
| **Frontend** | React / TypeScript | Moderne Oberfläche auf Port 3001 (via Docker). |
| **KI-Integration** | OpenAI GPT-4o | Intelligente Dateninterpretation und Diagnostik. |
| **Infrastruktur** | Docker Compose | Orchestrierung von Backend, Frontend und Postgres. |

---

## 🔧 Installation & Schnellstart

### Voraussetzungen
*   Docker & Docker Compose
*   Git
*   Optional: OpenAI API-Key (für die Analyse-Funktionen)
*   Optional: InfluxDB 2 Instanz (Datenquelle)

### System aktualisieren (Update)
Um Code-Änderungen (z. B. eine neue Version) in der Docker-Umgebung aktiv zu machen, führen Sie das Update-Skript aus:
```bash
scripts\update_system.bat
```
Dies stoppt die Container, baut die Images ohne Cache neu und startet das System neu.

### Schritte
1.  **Repository klonen:**
    ```bash
    git clone https://github.com/OliverRebock/HeizungsleserV2.git
    cd HeizungsleserV2
    ```
2.  **Konfiguration:**
    Kopieren Sie die `.env.example` Datei im Hauptverzeichnis nach `.env` und passen Sie die Werte an (insbesondere Passwörter und API-Keys).
    ```bash
    cp .env.example .env
    ```
3.  **System starten (via Docker Compose):**
    Starten Sie alle Dienste (Backend, Frontend, PostgreSQL) mit einem Befehl:
    ```bash
    docker-compose -f infra/docker-compose.yml up -d --build
    ```
4.  **Initialer Login & Zugriff:**
    *   **Frontend:** `http://localhost:3001` (Standard-Port für die Weboberfläche)
    *   **Backend API (Swagger):** `http://localhost:8000/docs`
    *   **Initialer Superuser:**
        *   Benutzer: `admin@example.com` (konfigurierbar via `FIRST_SUPERUSER`)
        *   Passwort: Das in der `.env` unter `FIRST_SUPERUSER_PASSWORD` gesetzte Passwort.

---

## 🎨 Branding & UX
Heizungsleser V2 setzt auf ein **"Clean Tech" Design**. Das minimalistische Branding stellt die Daten in den Vordergrund und sorgt für eine ablenkungsfreie Arbeitsumgebung auf Desktop- und Mobilgeräten.

---

© 2026 Oliver Rebock | Heizungsleser V2 – Intelligent Heating Management
