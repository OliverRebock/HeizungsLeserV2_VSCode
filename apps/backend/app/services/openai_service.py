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
                error_candidates_str += f"- Code: {cand['parsed_code']} (Typ: {cand['classification']}, Quelle: {cand['label']}, Rohwert: {cand['raw_value']})\n"
            logger.info(f"[{run_id}] Identified {len(candidates)} error candidates for OpenAI analysis.")

        system_prompt = f"""
Du bist ein Senior-Experte für Heizungssysteme und Wärmepumpen mit Spezialisierung auf technische Datenanalyse und Fehlerdiagnostik.
Deine Aufgabe ist es, die bereitgestellten Heizungsdaten eines konkreten Geräts tiefgreifend zu analysieren.

FACHLICHE PRIORITÄT (KRITISCH):
1. FEHLERCODES & ALARME: Suche gezielt nach Fehlernummern und Alarmmeldungen.
2. HISTORISCH VS AKTIV: Unterscheide streng zwischen historischen Fehlercodes (z.B. in 'last_error_code' oder mit '--' markiert) und aktuell aktiven Störungen.
3. GEWICHTUNG: Fehlerinformationen müssen am stärksten gewichtet werden.
4. DEKODIERUNG: Interpretiere unstrukturierte Strings wie '--(5140) 30.03.2026'. Die Zahl in Klammern (5140) ist der technische Code.
5. KORRELATION: Prüfe, ob Sensordaten (Vorlauf, Rücklauf, Druck) zum Fehlerbild passen.

Richtlinien für deine Analyse:
- Bewerte den Gesamtzustand. Wenn historische Fehler vorliegen, aber aktuell alles stabil ist, formuliere vorsichtig: "Historischer Fehlerhinweis erkannt, aktive Störung aktuell nicht sicher belegt".
- Benenne Fehlercodes explizit.
- Wenn keine Fehlercodes gefunden werden, analysiere Effizienz und Taktverhalten.
- Antworte strukturiert in {language} im JSON-Format.

JSON-Struktur der Antwort:
{{
  "summary": "Zusammenfassung unter Fokus auf Fehlercodes (historisch/aktiv) und Betriebszustand",
  "overall_status": "Status (optimal, unauffällig, beobachtungswürdig, auffällig, kritisch)",
  "detected_error_codes": [
    {{
      "code": "Extrahierter Code",
      "label": "Klartextmeldung / Typ",
      "source_entity": "Entity-ID",
      "source_label": "Sensorname",
      "observed_value": "Rohwert"
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
  "optimization_hints": ["Optimierungshinweis"],
  "recommended_followup_checks": ["Prüfschritte für den Techniker"],
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
5. Antworte in {language}.
6. Nutze das vorgegebene JSON-Format.

JSON-Struktur der Antwort:
{{
  "technical_summary": "Technische Zusammenfassung der Situation",
  "diagnostic_steps": ["Schritt 1", "Schritt 2"],
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
