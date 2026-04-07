# Heizungsleser V2 – Intelligente Heizungsüberwachung & Analyse

Heizungsleser V2 ist eine hochmoderne, mandantenfähige Plattform zur **Echtzeit-Überwachung**, **technischen Diagnose** und **KI-gestützten Optimierung** von Heizungssystemen (insbesondere Wärmepumpen). Die Anwendung schließt die Lücke zwischen komplexen Rohdaten aus Smart-Home-Systemen (wie Home Assistant) und verständlichen, handlungsorientierten Analysen für Fachbetriebe und Endkunden.

---

## 🌟 Warum Heizungsleser V2? (Vorteile)

*   **Effizienzsteigerung:** Identifizieren Sie unnötiges Takten und suboptimale Heizkurven, bevor sie zu hohen Stromrechnungen führen.
*   **KI-Expertise auf Knopfdruck:** Nutzen Sie die Power von OpenAI (GPT-4o), um komplexe Temperaturverläufe wie ein erfahrener Heizungstechniker interpretieren zu lassen.
*   **Mandantensicherheit (Multi-Tenancy):** Entwickelt für Dienstleister. Verwalten Sie hunderte Kunden in einer einzigen Oberfläche bei strikter Datentrennung.
*   **Herstellerunabhängig:** Durch die Anbindung an Home Assistant werden Daten verschiedenster Hersteller (Viessmann, Vaillant, Wolf, Buderus etc.) einheitlich verarbeitet.
*   **Zukunftssicher:** Modernster Tech-Stack (FastAPI, React, InfluxDB), der auf Performance und Skalierbarkeit ausgelegt ist.

---

## 🚀 Kernfunktionen im Detail

### 1. Rollenbasierte Benutzerverwaltung (RBAC)
Das System bildet die reale Hierarchie von Service-Strukturen ab:
*   **Plattform-Admin (Global):** Voller Zugriff. Kann Mandanten (Kunden) anlegen, Geräte registrieren und globale Systemparameter steuern.
*   **Mandanten-Admin (Kunde):** Kann innerhalb seines eigenen Kontingents Benutzer (Mitarbeiter oder Unterkunden) verwalten und deren Geräte überwachen.
*   **Endbenutzer (Tenant User):** Hat Zugriff auf das Dashboard und die Analysen seiner zugeordneten Heizungssysteme.
*   **Sicherheit:** Jeder API-Aufruf wird gegen die Mandanten-ID validiert (IDOR-Schutz).

### 2. Echtzeit-Monitoring & Dashboard
Verwandeln Sie Datenfriedhöfe in Erkenntnisse:
*   **Live-Metriken:** Vorlauf-, Rücklauf- und Außentemperaturen werden in Echtzeit aus InfluxDB visualisiert.
*   **Geräte-Zustand:** Sofortige Übersicht über den Online-Status und die Aktivität aller registrierten Instanzen.
*   **Interaktive Charts:** Zoomen Sie in Zeitreihen, um Schaltzyklen und Modulationsgrade präzise zu analysieren.

### 3. KI-Analyse & Fehlerdiagnose (Beta)
Das Herzstück der Anwendung:
*   **Automatisierte Reports:** Erstellen Sie auf Knopfdruck eine Zusammenfassung des Anlagenzustands. Die KI erkennt Muster, die in Tabellen verborgen bleiben.
*   **Deep Analysis:** Bei Verdacht auf Fehlfunktionen führt das System eine vertiefte technische Diagnose durch (unter Berücksichtigung von Herstellerspezifikationen).
*   **Optimierungsvorschläge:** Erhalten Sie konkrete Tipps zur Einstellung der Heizkurve oder zur Vermeidung von Effizienzverlusten.

### 4. Kunden- & Geräteverwaltung
Professionelles Management für Fachbetriebe:
*   **Mandanten-Scoping:** Geräte werden logisch Mandanten zugeordnet.
*   **InfluxDB Integration:** Jedes Gerät verfügt über dedizierte InfluxDB-Verbindungsdaten (Bucket, Token, URL) für maximale Flexibilität.

---

## 🛠️ Technologie-Stack

| Komponente | Technologie | Beschreibung |
| :--- | :--- | :--- |
| **Backend** | Python 3.12 / FastAPI | Hochperformante, asynchrone API-Verarbeitung. |
| **Datenbank (Meta)** | PostgreSQL | Verwaltung von Benutzern, Rollen und Mandantenstrukturen. |
| **Datenbank (Time)** | InfluxDB 2.x | Optimiert für Millionen von Messpunkten pro Sekunde. |
| **Frontend** | React / TypeScript | Moderne, reaktive Oberfläche mit Tailwind CSS. |
| **KI-Integration** | OpenAI GPT-4o | Intelligente Dateninterpretation und Diagnostik. |
| **Infrastruktur** | Docker Compose | Einfaches Deployment in Container-Umgebungen. |

---

## 🔧 Installation & Schnellstart

### Voraussetzungen
*   Docker & Docker Compose
*   Ein OpenAI API-Key (für die Analyse-Funktionen)
*   Git

### Schritte
1.  **Repository klonen:**
    ```bash
    git clone https://github.com/OliverRebock/HeizungsleserV2.git
    cd HeizungsleserV2
    ```
2.  **Konfiguration:**
    Kopieren Sie `infra/.env.example` nach `infra/.env` und passen Sie die Werte an (Datenbank-Passwörter, OpenAI Key).
3.  **System starten:**
    ```bash
    docker-compose -f infra/docker-compose.yml up -d --build
    ```
4.  **Initialer Login:**
    *   Öffnen Sie `http://localhost:3001`
    *   Standard-Admin: `admin@example.com` / `adminpassword` (Bitte umgehend ändern!)

---

## 🎨 Branding & UX
Heizungsleser V2 setzt auf ein **"Clean Tech" Design**. Das minimalistische Branding (v2.2.0) stellt die Daten in den Vordergrund und sorgt für eine ablenkungsfreie Arbeitsumgebung auf Desktop- und Mobilgeräten.

---

© 2026 Oliver Rebock | Heizungsleser V2 – Intelligent Heating Management
