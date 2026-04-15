# KI-Analyse (Beta) - Dokumentation

Dieses Dokument beschreibt die Implementierung und Funktionsweise der gerätebezogenen KI-Analyse im Heizungsleser V2.

## Übersicht

Die KI-Analyse ermöglicht eine datenbasierte Bewertung des Betriebszustands einer Heizung oder Wärmepumpe. Sie nutzt OpenAI (GPT-5.3), um Muster, Anomalien und Optimierungspotenziale in den Zeitreihendaten zu erkennen.

### Fehlercode-Interpretation (Schritt 7B/C Optimierung)

Ein Kernfeature der Analyse ist die automatische Erkennung und Interpretation von Fehlercodes:
- **Priorisierung:** Fehlerrelevante Entitäten (z.B. `last_error_code`, `fault`, `alarm`, `status`, `störung`, `meldung`) werden im `HeatingSummaryService` immer bevorzugt behandelt und an die KI gesendet, auch wenn sie nicht explizit vom Benutzer ausgewählt wurden.
- **Fehler-Extraktion (Deep Analysis):** Das Backend extrahiert mittels Regex gezielt Fehlercodes aus unstrukturierten Strings (z.B. `(5140)`) und stellt diese der KI in einer separaten Liste `detected_errors` zur Verfügung.
- **Mustererkennung:** Die KI (GPT-5.3) ist speziell darauf trainiert, diese vor-identifizierten Fehlercodes als höchste Priorität zu behandeln. Sie erkennt die technische Fehlernummer und den zeitlichen Bezug.
- **Gewichtung:** Im System-Prompt für GPT-5.3 ist festgelegt, dass Fehlercodes und Alarmmeldungen die stärkste Gewichtung in der Analyse erfahren müssen.

### Funktionsweise

1.  **Datenbezug:** Für ein ausgewähltes Gerät (`device_id`) werden die relevanten Entitäten aus **InfluxDB 2** geladen.
2.  **Vorverarbeitung:** Die Rohdaten werden im `HeatingSummaryService` verdichtet (Min, Max, Avg, Taktungs-Zähler, Status-Wechsel), um Token zu sparen und die Analyse zu fokussieren.
3.  **Klartextnamen:** Es werden bevorzugt `friendly_name` Attribute verwendet, damit die KI fachlich korrekte Bezeichnungen erhält (z.B. "Außentemperatur" statt "sensor.outdoor_temp").
4.  **OpenAI Integration:** Die verdichteten Daten werden an OpenAI gesendet. Die Antwort erfolgt im strukturierten JSON-Format.
5.  **Multi-Tenancy:** Der Zugriff ist strikt per RBAC geschützt. Nutzer können nur ihre eigenen Geräte analysieren.

## API-Endpunkte

### `POST /api/v1/analysis/{device_id}`

Startet eine Standard-Analyse für ein Gerät.

**Request Body:**

```json
{
  "from": "2026-03-25T00:00:00Z",
  "to": "2026-03-26T23:59:59Z",
  "analysis_focus": "Gesamtzustand, Effizienz und Taktung",
  "language": "de",
  "include_raw_summary": false
}
```

### Meilenstein 7: Optimierte Datenaufbereitung & Fehlererkennung

Die KI-Analyse wurde für eine präzisere Fehlererkennung und verbesserte Handhabung von Statuswerten optimiert:

1. **State-Erhaltung**: 
   - Entities wie Betriebsarten (`operating_mode`, `activity`) werden nicht mehr auf `0.0` normalisiert.
   - Stattdessen wird eine `state summary` erzeugt, die Textzustände (`Heizen`, `Manuell`, `auto`) direkt an OpenAI überträgt.

2. **Fehlercode-Parsing (Deep Extraction)**:
   - Komplexe Strings wie `--(5140) 30.03.2026` werden serverseitig geparst.
   - Der technische Code `5140` wird extrahiert.
   - Fehler werden automatisch in `historical` (mit `--` oder `last` im Namen) und `active` klassifiziert.

3. **Error Candidates & Gewichtung**:
   - Das Backend identifiziert vorab `error_candidates` und hebt diese im Prompt für GPT-5.3 hervor.
   - GPT-5.3 ist angewiesen, historische Fehler von aktiven Störungen zu unterscheiden und Diagnosen vorsichtig zu formulieren ("Historischer Fehlerhinweis erkannt, aktive Störung aktuell nicht sicher belegt").

4. **Debugging & Traceability**:
   - Jede Analyse erhält eine eindeutige `analysis_run_id`.
   - Diese ID wird in den Backend-Logs zusammen mit dem exakten OpenAI-Payload protokolliert, um Analysen jederzeit nachvollziehen zu können.

5. **Trigger für Folgeanalyse**:
   - Wenn das Backend oder die KI signifikante Fehlerkandidaten erkennt, wird `should_trigger_error_analysis` auf `true` gesetzt, was im Frontend die Option zur vertieften Fehleranalyse aktiviert.

### `POST /api/v1/analysis/{device_id}/deep` (Schritt 7C)

Startet eine vertiefte technische Fehleranalyse. Dieser Endpunkt wird typischerweise aufgerufen, wenn die Standard-Analyse kritische Muster erkennt (`should_trigger_error_analysis: true`).

**Besonderheiten:**
- Verwendet einen spezialisierten Prompt für technische Diagnose.
- Analysiert bevorzugt Fehlercodes und unplausible Sensorwerte.
- Liefert `diagnostic_steps` (konkrete Prüfschritte für Techniker) und `suspected_causes`.
- Standard-Zeitraum: 7 Tage (um Muster besser zu erkennen).

**Response:**
Siehe `DeepAnalysisResponse` Schema.

## Konfiguration (Environment Variables)

Folgende Variablen müssen in der `.env` gesetzt sein:

*   `OPENAI_API_KEY`: Dein OpenAI API Key.
*   `OPENAI_MODEL_PRIMARY`: Aktuell auf `gpt-5.3` konfiguriert.
*   `OPENAI_TIMEOUT_SECONDS`: Timeout für den API-Aufruf (Standard: 60s).
*   `OPENAI_ANALYSIS_ENABLED`: Muss auf `true` stehen.

## Grenzen der Analyse

*   Die KI führt keine technische Diagnose im rechtlichen Sinne durch.
*   Die Ergebnisse sind als "Einschätzungen" und "Beobachtungen" zu verstehen.
*   Fehlende Daten in InfluxDB führen zu unvollständigen Analysen.

## Ausblick: Fehleranalyse (Schritt 7C)

Die aktuelle Implementierung ist die **Primäranalyse**. Wenn das Feld `should_trigger_error_analysis` auf `true` gesetzt wird, kann in einer späteren Ausbaustufe eine tiefere, fehlerfokussierte Analyse (Schritt 7C) angestoßen werden. Diese wird dann gezielt nach bekannten Fehlermustern suchen.

## Frontend-Integration (Schritt 7B)

Die KI-Analyse ist im Frontend über den Menüpunkt **KI-Analyse (Beta)** erreichbar.

### Funktionen im Frontend:
- **Geräte-Auswahl:** Benutzer können aus den ihnen zugewiesenen Geräten (RBAC-gesichert) wählen.
- **Zeitraum-Auswahl:** Vordefinierte Intervalle (24h, 7d, 30d) oder benutzerdefinierte Zeiträume.
- **Analyse-Start:** Auslösung des Backend-Calls mit Ladeanzeige.
- **Ergebnis-Darstellung:** Strukturierte Anzeige der KI-Ergebnisse mit Karten für Findings, Anomalien und Optimierungshinweise.
- **Vertiefte Fehleranalyse (Schritt 7C):** Wenn kritische Muster erkannt werden, kann eine technische Tiefenanalyse gestartet werden. Diese zeigt diagnostische Schritte und vermutete Ursachen in einem speziellen High-Tech-Layout an.
- **Status-Visualisierung:** Farbliches Feedback basierend auf dem `overall_status`.

### Technische Details (Frontend):
- **Route:** `/analysis`
- **Komponente:** `AnalysisPage.tsx`
- **Service:** Nutzt den standardmäßigen `api` Service (Axios) und `react-query` (`useMutation`) für den asynchronen Aufruf.
- **Icons:** Verwendung von `lucide-react` (Brain, Activity, AlertTriangle etc.) für eine klare visuelle Trennung.
