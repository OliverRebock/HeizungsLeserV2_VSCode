import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

STATUS_PRIORITY = {
    "optimal": 0,
    "unauffällig": 1,
    "beobachtungswürdig": 2,
    "auffällig": 3,
    "kritisch": 4,
}


class LocalAnalysisService:
    def _build_seen_text(self, candidate: Dict[str, Any]) -> Optional[str]:
        first_seen_at = candidate.get("first_seen_at")
        last_seen_at = candidate.get("last_seen_at")
        seen_count = int(candidate.get("seen_count", 1) or 1)

        if not first_seen_at and not last_seen_at:
            return None

        if first_seen_at and last_seen_at and first_seen_at != last_seen_at:
            base_text = f"Im gewählten Zeitraum gesehen von {first_seen_at} bis {last_seen_at}"
        else:
            base_text = f"Im gewählten Zeitraum gesehen: {first_seen_at or last_seen_at}"

        if seen_count > 1:
            return f"{base_text} ({seen_count} Messpunkte)"
        return base_text

    def build_analysis(
        self,
        summary_data: Dict[str, Any],
        focus: Optional[str] = None,
        fallback_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        entities = summary_data.get("entities", [])
        error_candidates = summary_data.get("error_candidates", [])

        findings: List[Dict[str, Any]] = []
        anomalies: List[Dict[str, str]] = []
        optimization_hints: List[str] = []
        followup_checks: List[str] = []
        detected_error_codes: List[Dict[str, str]] = []
        overall_status = "unauffällig"

        for candidate in error_candidates:
            code = str(candidate.get("parsed_code") or "unbekannt")
            label = candidate.get("label") or candidate.get("entity_id") or "Unbekannter Sensor"
            classification = str(candidate.get("classification") or "unknown").lower()
            raw_value = str(candidate.get("raw_value") or "")
            seen_text = self._build_seen_text(candidate)

            if classification == "active":
                severity = "critical"
                status_target = "kritisch"
                description = (
                    f"Ein aktiver Fehlerhinweis wurde erkannt. Der Wert '{raw_value}' sollte "
                    "als aktuelle Störung oder Warnung eingeordnet und zeitnah geprüft werden."
                )
            elif classification == "historical":
                severity = "medium"
                status_target = "beobachtungswürdig"
                description = (
                    f"Der Wert '{raw_value}' deutet auf einen historischen Fehler hin. Eine "
                    "aktuelle Störung ist damit nicht sicher belegt, das Muster sollte aber beobachtet werden."
                )
            else:
                severity = "high"
                status_target = "auffällig"
                description = (
                    f"Der Wert '{raw_value}' enthält einen auffälligen Fehler- oder Alarmhinweis, "
                    "der technisch eingeordnet werden sollte."
                )

            detected_error_codes.append(
                {
                    "code": code,
                    "label": label,
                    "source_entity": str(candidate.get("entity_id") or ""),
                    "source_label": label,
                    "observed_value": raw_value,
                    "first_seen_at": candidate.get("first_seen_at"),
                    "last_seen_at": candidate.get("last_seen_at"),
                    "seen_count": int(candidate.get("seen_count", 1) or 1),
                }
            )
            findings.append(
                {
                    "title": f"Fehlercode {code} erkannt",
                    "severity": severity,
                    "description": description,
                    "evidence": [
                        f"Quelle: {label}",
                        f"Rohwert: {raw_value}",
                        *( [seen_text] if seen_text else [] ),
                    ],
                }
            )
            followup_checks.extend(
                [
                    f"Fehlerhistorie zu Code {code} am Regler oder im Service-Menü prüfen.",
                    f"Den betroffenen Sensor bzw. Statuskanal '{label}' im Detailverlauf kontrollieren.",
                ]
            )
            overall_status = self._escalate_status(overall_status, status_target)

        numeric_entities = 0
        state_entities = 0

        for entity in entities:
            entity_summary = entity.get("summary") or {}
            label = entity.get("label") or entity.get("entity_id") or "Unbekannte Entität"

            if self._is_numeric_summary(entity_summary):
                numeric_entities += 1
                min_value = float(entity_summary.get("min", 0))
                max_value = float(entity_summary.get("max", 0))
                avg_value = float(entity_summary.get("avg", 0))
                count = int(entity_summary.get("count", 0) or 0)
                spread = abs(max_value - min_value)
                relative_spread = spread / abs(avg_value) if avg_value not in (0, 0.0) else None

                if count >= 8 and (
                    (relative_spread is not None and relative_spread >= 0.6)
                    or spread >= 10
                ):
                    anomalies.append(
                        {
                            "title": f"Starke Schwankung bei {label}",
                            "description": (
                                f"Die Messreihe bewegt sich zwischen {round(min_value, 2)} und "
                                f"{round(max_value, 2)} bei einem Mittelwert von {round(avg_value, 2)}."
                            ),
                        }
                    )
                    findings.append(
                        {
                            "title": f"Unruhiger Verlauf bei {label}",
                            "severity": "medium",
                            "description": (
                                "Die lokale Auswertung erkennt einen stark variierenden Verlauf. "
                                "Das kann zu Taktung, instabilen Betriebszuständen oder ungleichmäßiger Wärmeabgabe passen."
                            ),
                            "evidence": [
                                f"Min/Max: {round(min_value, 2)} / {round(max_value, 2)}",
                                f"Mittelwert: {round(avg_value, 2)}",
                                f"Datenpunkte: {count}",
                            ],
                        }
                    )
                    optimization_hints.append(
                        f"{label}: Regelung, Volumenstrom und Sensorplausibilität auf Ursache für die Schwankung prüfen."
                    )
                    followup_checks.append(
                        f"Zeitlichen Verlauf von '{label}' gemeinsam mit Verdichter-/Pumpenstatus prüfen."
                    )
                    overall_status = self._escalate_status(overall_status, "beobachtungswürdig")
            else:
                state_entities += 1
                changes = int(entity_summary.get("changes", 0) or 0)
                count = int(entity_summary.get("count", 0) or 0)

                if count >= 6 and changes >= max(6, count // 3):
                    findings.append(
                        {
                            "title": f"Häufige Zustandswechsel bei {label}",
                            "severity": "medium",
                            "description": (
                                "Die Zustandsdaten wechseln im gewählten Zeitraum auffällig oft. "
                                "Das spricht für ein unruhiges Betriebsverhalten oder wiederkehrende Umschaltungen."
                            ),
                            "evidence": [
                                f"Wechsel: {changes}",
                                f"Beobachtungen: {count}",
                            ],
                        }
                    )
                    anomalies.append(
                        {
                            "title": f"Unruhiger Statusverlauf bei {label}",
                            "description": f"Es wurden {changes} Zustandswechsel in {count} Beobachtungen erkannt.",
                        }
                    )
                    optimization_hints.append(
                        f"{label}: Prüfen, ob die vielen Umschaltungen fachlich erwartbar sind oder auf Taktung hindeuten."
                    )
                    overall_status = self._escalate_status(overall_status, "beobachtungswürdig")

        if not findings:
            findings.append(
                {
                    "title": "Kein akuter Störhinweis erkannt",
                    "severity": "low",
                    "description": (
                        "Die lokale Auswertung erkennt im gewählten Zeitraum keine klaren Fehlercodes "
                        "und keine starken Auffälligkeiten in den verdichteten Daten."
                    ),
                    "evidence": [
                        f"Ausgewertete Entitäten: {len(entities)}",
                    ],
                }
            )
            overall_status = self._escalate_status(overall_status, "unauffällig")

        if not optimization_hints:
            optimization_hints.extend(
                [
                    "Regelmäßig Vorlauf, Rücklauf und Betriebsstatus gemeinsam beobachten, um schleichende Abweichungen früh zu erkennen.",
                    "Für eine präzisere Ursachenanalyse bei Bedarf den Zeitraum erweitern und Fehler-/Statussensoren gezielt auswählen.",
                ]
            )

        if not followup_checks:
            followup_checks.extend(
                [
                    "Gerätestatus und Fehlerhistorie im Anlagenregler gegenprüfen.",
                    "Auffällige Kanäle im Rohdatenverlauf auf Zeitkorrelationen prüfen.",
                ]
            )

        confidence = "high" if len(entities) >= 8 else "medium" if len(entities) >= 3 else "low"
        focus_text = f" mit Fokus auf {focus}" if focus else ""
        summary_parts = [
            f"Die lokale Analyse hat {len(entities)} Datenkanäle{focus_text} ausgewertet.",
        ]
        if error_candidates:
            summary_parts.append(
                f"Es wurden {len(error_candidates)} Fehler- oder Alarmhinweise erkannt."
            )
        elif anomalies:
            summary_parts.append("Es zeigen sich mehrere Auffälligkeiten im Betriebsverhalten.")
        else:
            summary_parts.append("Der aggregierte Verlauf wirkt insgesamt eher stabil.")
        if fallback_reason:
            summary_parts.append(
                "Die Einschätzung basiert auf lokalen Regeln, weil der KI-Dienst nicht genutzt werden konnte."
            )

        return {
            "summary": " ".join(summary_parts),
            "overall_status": overall_status,
            "detected_error_codes": detected_error_codes,
            "findings": findings,
            "anomalies": anomalies,
            "optimization_hints": self._dedupe(optimization_hints),
            "recommended_followup_checks": self._dedupe(followup_checks),
            "confidence": confidence,
            "should_trigger_error_analysis": bool(error_candidates),
            "analysis_mode": "fallback",
            "analysis_notice": self._build_notice(fallback_reason),
        }

    def build_deep_analysis(
        self,
        summary_data: Dict[str, Any],
        manufacturer: Optional[str],
        heat_pump_type: Optional[str],
        fallback_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        base_analysis = self.build_analysis(
            summary_data=summary_data,
            focus="technische Fehlerdiagnose",
            fallback_reason=fallback_reason,
        )
        error_candidates = summary_data.get("error_candidates", [])

        suspected_causes: List[str] = []
        diagnostic_steps: List[str] = []
        technical_findings: List[Dict[str, Any]] = []

        for candidate in error_candidates:
            code = str(candidate.get("parsed_code") or "unbekannt")
            label = candidate.get("label") or candidate.get("entity_id") or "Unbekannter Sensor"
            classification = str(candidate.get("classification") or "unknown").lower()

            if classification == "active":
                suspected_causes.append(
                    f"Aktiver Fehlercode {code} an '{label}' deutet auf eine aktuell wirksame Störung oder Schutzabschaltung hin."
                )
            elif classification == "historical":
                suspected_causes.append(
                    f"Historischer Fehlercode {code} an '{label}' weist auf eine wiederkehrende frühere Störung hin."
                )
            else:
                suspected_causes.append(
                    f"Der auffällige Statuswert '{code}' an '{label}' sollte herstellerspezifisch interpretiert werden."
                )

            diagnostic_steps.extend(
                [
                    f"Service-Menü und Fehlerspeicher für Code {code} am Gerät auslesen.",
                    f"Den Kanal '{label}' zeitlich mit Pumpen-, Verdichter- und Temperaturwerten korrelieren.",
                ]
            )

        for finding in base_analysis["findings"]:
            technical_findings.append(
                {
                    "title": finding["title"],
                    "severity": finding["severity"],
                    "description": finding["description"],
                    "evidence": finding["evidence"],
                }
            )

        if not suspected_causes:
            suspected_causes.append(
                "Ohne klaren Fehlercode deutet die lokale Analyse eher auf betriebliche Unruhe oder einen regelungstechnischen Effekt als auf einen eindeutigen Komponentendefekt hin."
            )

        diagnostic_steps.extend(
            [
                "Hydraulik, Volumenstrom und Fühlerwerte auf Plausibilität prüfen.",
                "Bei wiederkehrenden Auffälligkeiten den Analysezeitraum auf mindestens 7 bis 30 Tage erweitern.",
            ]
        )

        manufacturer_part = manufacturer or "unbekanntem Hersteller"
        type_part = heat_pump_type or "unbekanntem Typ"
        technical_summary = (
            f"Die vertiefte lokale Analyse für {manufacturer_part} / {type_part} basiert auf "
            f"{len(summary_data.get('entities', []))} verdichteten Datenkanälen."
        )
        if error_candidates:
            technical_summary += (
                f" Es wurden {len(error_candidates)} technische Fehlerhinweise erkannt, "
                "die eine gezielte Prüfung am Gerät rechtfertigen."
            )
        else:
            technical_summary += (
                " Es liegen keine eindeutig dekodierbaren Fehlercodes vor, daher stehen Verlaufsmuster und Zustandswechsel im Vordergrund."
            )
        if fallback_reason:
            technical_summary += " Der KI-Dienst war nicht nutzbar, deshalb wurde eine regelbasierte Auswertung verwendet."

        return {
            "technical_summary": technical_summary,
            "diagnostic_steps": self._dedupe(diagnostic_steps),
            "suspected_causes": self._dedupe(suspected_causes),
            "technical_findings": technical_findings,
            "confidence": "medium" if error_candidates else "low",
            "analysis_mode": "fallback",
            "analysis_notice": self._build_notice(fallback_reason),
        }

    def _build_notice(self, fallback_reason: Optional[str]) -> Optional[str]:
        if not fallback_reason:
            return None
        return (
            f"Lokale Auswertung aktiv: {fallback_reason} "
            "Die Ergebnisse basieren auf heuristischen Regeln und sind weniger präzise als eine KI-Analyse."
        )

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _is_numeric_summary(self, summary: Dict[str, Any]) -> bool:
        required_keys = {"min", "max", "avg", "count"}
        return required_keys.issubset(summary.keys())

    def _escalate_status(self, current_status: str, new_status: str) -> str:
        current_priority = STATUS_PRIORITY.get(current_status, 1)
        new_priority = STATUS_PRIORITY.get(new_status, current_priority)
        return new_status if new_priority > current_priority else current_status


local_analysis_service = LocalAnalysisService()
