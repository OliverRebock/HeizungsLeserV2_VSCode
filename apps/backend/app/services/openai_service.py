import json
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.schemas.analysis import AnalysisResponse

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL_PRIMARY
        self.timeout = settings.OPENAI_TIMEOUT_SECONDS
        self.enabled = settings.OPENAI_ANALYSIS_ENABLED and bool(self.api_key)

        logger.info(f"OpenAI Service initialized: model={self.model}, enabled={self.enabled}")

    async def analyze_heating_data(self, summary_data: Dict[str, Any], focus: str, language: str = "de") -> Dict[str, Any]:
        if not self.enabled:
            logger.warning("KI-Analyse requested but service is disabled or API key missing.")
            raise ValueError("KI-Analyse ist deaktiviert oder kein OpenAI API-Key konfiguriert.")

        run_id = summary_data.get("analysis_run_id", "unknown")
        logger.info(f"[{run_id}] Starting KI-Analysis for device {summary_data.get('device_name')} using {self.model}. Focus: {focus}")
        
        error_candidates_str = ""
        if "error_candidates" in summary_data and summary_data["error_candidates"]:
            candidates = summary_data["error_candidates"]
            error_candidates_str = "WICHTIG: Folgende FEHLER-KANDIDATEN wurden in den Rohdaten identifiziert:\n"
            for cand in candidates:
                seen_from = cand.get("first_seen_at")
                seen_to = cand.get("last_seen_at")
                seen_count = cand.get("seen_count")
                seen_text = ""
                if seen_from and seen_to and seen_from != seen_to:
                    seen_text = f", gesehen von {seen_from} bis {seen_to}"
                elif seen_from or seen_to:
                    seen_text = f", gesehen am {seen_from or seen_to}"
                if seen_count and int(seen_count) > 1:
                    seen_text += f" ({seen_count} Messpunkte)"

                error_candidates_str += (
                    f"- Code: {cand['parsed_code']} "
                    f"(Typ: {cand['classification']}, Quelle: {cand['label']}, Rohwert: {cand['raw_value']}{seen_text})\n"
                )
            logger.info(f"[{run_id}] Identified {len(candidates)} error candidates for OpenAI analysis.")

        system_prompt = f"""
Du bist ein Senior-Experte für Heizungssysteme und Wärmepumpen mit Spezialisierung auf technische Datenanalyse und Fehlerdiagnostik.
Deine Aufgabe ist es, die bereitgestellten Heizungsdaten eines konkreten Geräts so zu analysieren, dass ein Heizungsbauer beim Kunden schnell eine brauchbare erste Antwort erhält.

FACHLICHE PRIORITÄT (KRITISCH):
1. FEHLERCODES & ALARME: Suche gezielt nach Fehlernummern und Alarmmeldungen.
2. HISTORISCH VS AKTIV: Unterscheide streng zwischen historischen Fehlercodes (z.B. in 'last_error_code' oder mit '--' markiert) und aktuell aktiven Störungen.
3. EFFIZIENZMETRIKEN: Bewerte **Spreizung, Zyklushäufigkeit und WW-Anteil** wie ein Heizungsbauer:
   - **Spreizung (K)**: Sollte 5–8 K sein. Zu klein (<3 K) = zu hoher Volumenstrom. Zu groß (>10 K) = ineffizient.
   - **Starts pro Tag**: <3 ist normal. >8 = auffälliges Takten. 3–5 = erhöht, aber tolerabel.
   - **Warmwasser-Anteil**: >35% bedeutet häufige WW-Umschaltungen — WW-Solltemperatur prüfen?
   - **Durchschn. Phasenlänge**: Lang (>5h) ist normal für WP. Kurz (<1h) deutet auf Takten hin.
4. DEKODIERUNG: Interpretiere unstrukturierte Strings wie '--(5140) 30.03.2026'. Die Zahl in Klammern (5140) ist der technische Code.
5. KORRELATION: Prüfe, ob Sensordaten (Vorlauf, Rücklauf, Druck, Spreizung) zum Fehlerbild oder der Betriebsart passen.

HEIZUNGSBAUER-SPEZIFISCHE FRAGEN IN FOLLOW-UP-CHECKS:
- Spreizung zu klein? → "Volumenstrompumpe und Regulierung prüfen"
- Häufiges Takten? → "Speichergröße, Regelung und Hysterese überprüfen"
- Hoher WW-Anteil? → "WW-Solltemperatur und Schichtladung analysieren"
- Höhere Verdichtertemperatur? → "Verdichterfrequenz und Öltemperatur dokumentieren"

Richtlinien für deine Analyse:
- Bewerte den Gesamtzustand. Wenn historische Fehler vorliegen, aber aktuell alles stabil ist, formuliere vorsichtig: "Historischer Fehlerhinweis erkannt, aktive Störung aktuell nicht sicher belegt".
- Benenne Fehlercodes explizit.
- Wenn keine Fehlercodes gefunden werden, analysiere **Effizienz, Spreizung und Taktverhalten** wie ein Techniker.
- Nutze die dynamischen Betriebskontexte aus `operating_context` (Statusfenster, Temperatur-Peaks, efficiency_metrics) um Aussagen faktenbasiert zu treffen.
- Vermeide starre Entitaetsannahmen: leite Betriebsmodus aus bereitgestellten Kontextdaten ab, nicht aus festen Entity-IDs.
- Antworte kurz, direkt und praxisnah — als würde ein Techniker beim Kunden vor Ort entscheiden.
- Die Zusammenfassung soll maximal 2 kurze Sätze umfassen.
- Nenne höchstens 3 Findings, höchstens 2 Anomalien, höchstens 3 Optimierungshinweise und höchstens 4 Follow-up-Checks.
- In Follow-up-Checks: konkrete Techniker-Aktionen statt allgemeiner Aussagen (z.B. "Verdichterfrequenz in Bedienoberfläche prüfen" statt "Effizienz prüfen").
- `should_trigger_error_analysis` nur auf `true` setzen, wenn eine vertiefte Ursachenanalyse für eine kritische oder unklare Störung wirklich sinnvoll ist.
- Antworte strukturiert in {language} im JSON-Format.

JSON-Struktur der Antwort:
{{
  "summary": "Kurze Zusammenfassung in maximal 2 Sätzen",
  "overall_status": "Status (optimal, unauffällig, beobachtungswürdig, auffällig, kritisch)",
  "detected_error_codes": [
    {{
      "code": "Extrahierter Code",
      "label": "Klartextmeldung / Typ",
      "source_entity": "Entity-ID",
      "source_label": "Sensorname",
      "observed_value": "Rohwert",
      "first_seen_at": "Wann im ausgewählten Zeitraum zuerst gesehen",
      "last_seen_at": "Wann im ausgewählten Zeitraum zuletzt gesehen",
      "seen_count": 1
    }}
  ],
  "findings": [
    {{
      "title": "Titel",
      "severity": "low/medium/high/critical",
      "description": "Fachliche Bedeutung? Historisch oder Aktiv?",
      "evidence": ["Datenpunkt als Beweis"]
    }}
  ],
  "anomalies": [{{ "title": "Anomalie", "description": "Beschreibung" }}],
  "optimization_hints": ["Nur sofort hilfreiche Hinweise"],
  "recommended_followup_checks": ["Kurze Prüfschritte für den Techniker"],
  "confidence": "low/medium/high",
  "should_trigger_error_analysis": true/false
}}
"""

        user_content = f"""
Analyse-Fokus: {focus}
Run-ID: {run_id}

{error_candidates_str}

Hier sind die aufbereiteten Daten des Geräts:
{json.dumps(summary_data, indent=2)}
"""

        logger.info(f"[{run_id}] Sending request to OpenAI (Model: {self.model})...")
        logger.debug(f"[{run_id}] User Content (Data sent to OpenAI): {user_content}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.info(f"Sending request to OpenAI (Model: {self.model})...")
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                )
                logger.info(f"OpenAI response received. Status: {response.status_code}")
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                logger.debug(f"Raw content from OpenAI: {content[:500]}...")
                
                # Parsing the JSON from OpenAI
                analysis_dict = json.loads(content)
                logger.info("Successfully parsed KI-analysis result.")
                return analysis_dict
                
            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"Fehler bei der Kommunikation mit OpenAI: {e.response.status_code}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI JSON response: {e}")
                raise Exception("Die KI hat eine ungültige Antwort geliefert.")
            except Exception as e:
                logger.exception(f"Unexpected error in OpenAIService: {e}")
                raise Exception(f"Ein unerwarteter Fehler ist bei der KI-Analyse aufgetreten: {str(e)}")

    async def analyze_error_patterns(
        self, 
        summary_data: Dict[str, Any], 
        focus: str, 
        language: str = "de",
        manufacturer: Optional[str] = None,
        heat_pump_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Specialized AI analysis for deep technical diagnostics and error code interpretation.
        """
        if not self.enabled:
            raise ValueError("KI-Analyse ist deaktiviert.")

        logger.info(f"Starting Deep Technical Analysis for {manufacturer} {heat_pump_type}. Focus: {focus}")

        manufacturer_context = f"Hersteller: {manufacturer}\n" if manufacturer else ""
        type_context = f"Wärmepumpentyp: {heat_pump_type}\n" if heat_pump_type else ""

        system_prompt = f"""
Du bist ein hochqualifizierter Diagnosetechniker für Heizungssysteme und Wärmepumpen.
Deine Aufgabe ist eine vertiefte technische Fehleranalyse basierend auf Sensordaten und Fehlercodes.

GERÄTEKONTEXT:
{manufacturer_context}{type_context}
Nutze dein Wissen über diesen spezifischen Hersteller und Typ, um Fehlercodes und Betriebsmuster präziser zu deuten.

WICHTIG - Fehlercode-Dekodierung:
- Analysiere kryptische Fehler-Strings wie '--(5140) 30.03.2026 15:55-30.03.2026 16:00'.
- Die Zahl in Klammern (hier 5140) ist oft die technische Fehlernummer.
- Zeitstempel geben an, wann der Fehler aufgetreten oder verschwunden ist.
- Setze diese Codes in Bezug zu Sensordaten (z.B. Fehlermeldung 5140 korreliert mit Stillstand der Pumpe).

Richtlinien:
1. Analysiere Fehlercodes, Warnungen und unplausible Sensorwerte (z.B. extreme Spreizung, stehende Pumpen, Sensorfehler).
2. Suche nach zeitlichen Korrelationen zwischen Fehlern und Betriebszuständen (z.B. Fehler tritt immer bei Verdichterstart auf).
3. Erstelle eine Liste von konkreten diagnostischen Schritten, die ein Techniker vor Ort durchführen sollte.
4. Nenne vermutete Ursachen mit Angabe der Wahrscheinlichkeit.
5. Antworte kompakt und priorisiere nur die technisch wichtigsten Punkte.
6. Verwende maximal 2 kurze Sätze für `technical_summary`, maximal 3 `suspected_causes`, maximal 5 `diagnostic_steps` und maximal 3 `technical_findings`.
7. Antworte in {language}.
8. Nutze das vorgegebene JSON-Format.

JSON-Struktur der Antwort:
{{
  "technical_summary": "Kurze technische Zusammenfassung in maximal 2 Sätzen",
  "diagnostic_steps": ["Kurzer Schritt 1", "Kurzer Schritt 2"],
  "suspected_causes": ["Ursache A (hohe Wahrscheinlichkeit)", "Ursache B"],
  "technical_findings": [
    {{
      "title": "Technischer Befund",
      "severity": "medium/high/critical",
      "description": "Detaillierte Analyse",
      "evidence": ["Datenpunkt X zeigt Y"]
    }}
  ],
  "confidence": "low/medium/high"
}}
"""
        user_content = f"""
Analyse-Fokus: {focus}
Hersteller: {manufacturer or 'unbekannt'}
Modell/Typ: {heat_pump_type or 'unbekannt'}

Daten:
{json.dumps(summary_data, indent=2)}
"""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    }
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)
            except Exception as e:
                logger.exception(f"Deep analysis failed: {e}")
                raise Exception(f"Die vertiefte Analyse ist fehlgeschlagen: {str(e)}")

openai_service = OpenAIService()
