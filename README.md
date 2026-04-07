# Heizungsleser V2 – Intelligente Heizungsüberwachung & Analyse

Heizungsleser V2 ist eine moderne Multi-Mandanten-Plattform zur Echtzeit-Überwachung und KI-gestützten Analyse von Heizungssystemen. Die Anwendung ermöglicht es Dienstleistern und Endkunden, Verbrauchsdaten zu visualisieren, Betriebszustände zu überwachen und durch künstliche Intelligenz Optimierungspotenziale zu identifizieren.

## 🚀 Kernfunktionen

### 👤 Rollenbasierte Benutzerverwaltung (RBAC)
*   **Plattform-Admin:** Vollständige Kontrolle über alle Mandanten, Benutzer und globale Gerätekonfigurationen.
*   **Mandanten-Admin:** Verwaltung von Benutzern und Geräten innerhalb des eigenen Mandanten (Kundenbereichs).
*   **Benutzer:** Zugriff auf Dashboards und Analysen der zugeordneten Geräte.
*   **Sicherheit:** Strikte Datentrennung (Multi-Tenancy) stellt sicher, dass Kunden nur ihre eigenen Daten sehen.

### 📊 Echtzeit-Monitoring & Dashboard
*   Visualisierung von Heizungsdaten (Vorlauf-/Rücklauftemperatur, Pumpenstatus, etc.) über InfluxDB.
*   Interaktive Diagramme zur Verlaufsanalyse.
*   Live-Statusanzeige der registrierten Home-Assistant-Instanzen.

### 🤖 KI-Analyse (Beta)
*   Anbindung an OpenAI (GPT-4) zur Interpretation komplexer Heizungsverläufe.
*   Automatisierte Erkennung von Ineffizienzen oder Fehlkonfigurationen.
*   Vorschläge zur Energieeinsparung basierend auf realen Messwerten.

### 🏢 Mandanten- & Geräteverwaltung
*   Einfaches Onboarding neuer Kunden (Mandanten).
*   Flexible Zuordnung von Geräten zu spezifischen Kundenbereichen.
*   Eindeutige Identifikation über InfluxDB-Buckets und Token.

## 🛠️ Technologie-Stack

*   **Backend:** Python 3.12, FastAPI (Asynchron), SQLAlchemy 2.0.
*   **Frontend:** React 18, TypeScript, Tailwind CSS, TanStack Query (v5), Lucide Icons.
*   **Datenbanken:** PostgreSQL (Metadaten), InfluxDB 2.x (Zeitreihendaten).
*   **KI-Engine:** OpenAI API (GPT-4o).
*   **Infrastruktur:** Docker & Docker Compose für containerisierte Bereitstellung.

## 🔧 Installation & Start

### Voraussetzungen
*   Docker & Docker Compose
*   Git

### Schritte
1.  **Repository klonen:**
    ```bash
    git clone https://github.com/OliverRebock/HeizungsleserV2.git
    cd HeizungsleserV2
    ```
2.  **Umgebungsvariablen:**
    Kopieren Sie die `.env.example` nach `.env` und tragen Sie Ihre API-Keys (z.B. OpenAI) ein.
3.  **Start über Docker:**
    ```bash
    docker-compose -f infra/docker-compose.yml up -d --build
    ```
4.  **Zugriff:**
    *   Frontend: `http://localhost:3001`
    *   Backend-API: `http://localhost:8000/docs` (Swagger UI)

## 🎨 Branding
Die Anwendung verfügt über ein integriertes, modernes Branding (Logo & Design-System v2.2.0), das speziell für technische Dashboards optimiert wurde.

---
© 2024 Oliver Rebock | Heizungsleser V2
