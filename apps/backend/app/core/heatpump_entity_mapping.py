from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class IntentEntityProfile:
    intent: str
    entity_keywords: List[str]
    question_keywords: List[str]
    fallback_entity_limit: int = 8


INTENT_ENTITY_PROFILES: Dict[str, IntentEntityProfile] = {
    "cycling": IntentEntityProfile(
        intent="cycling",
        entity_keywords=[
            "verdichter",
            "compressor",
            "start",
            "starts",
            "laufzeit",
            "runtime",
            "betrieb",
            "status",
            "state",
            "takt",
            "on",
            "off",
        ],
        question_keywords=["takt", "haeufig", "haeufigkeit", "häufig", "starts"],
    ),
    "flow": IntentEntityProfile(
        intent="flow",
        entity_keywords=[
            "durchfluss",
            "flow",
            "volumenstrom",
            "pc0",
            "pc1",
            "pumpe",
        ],
        question_keywords=["durchfluss", "flow", "pc0", "pc1", "volumenstrom"],
    ),
    "last_off": IntentEntityProfile(
        intent="last_off",
        entity_keywords=[
            "status",
            "state",
            "betrieb",
            "verdichter",
            "compressor",
            "on",
            "off",
            "running",
        ],
        question_keywords=["zuletzt", "aus", "ausgegangen", "off", "abgeschaltet"],
    ),
    "hot_water": IntentEntityProfile(
        intent="hot_water",
        entity_keywords=[
            "warmwasser",
            "dhw",
            "ww",
            "boiler",
            "tank",
            "speicher",
            "tap_water",
            "tapwater_active",
            "dhw_current_intern_temperature",
            "dhw_starts",
            "dhw_energy_consumption_compressor",
        ],
        question_keywords=[
            "warmwasser",
            "dhw",
            "ww",
            "boiler",
            "speicher",
            "wasser",
            "aufgeheizt",
            "aufgewaermt",
            "aufgewärmt",
            "wann",
            "gestern",
            "uhrzeit",
        ],
    ),
    "anomaly": IntentEntityProfile(
        intent="anomaly",
        entity_keywords=[
            "fehler",
            "error",
            "alarm",
            "fault",
            "stoer",
            "stör",
            "code",
            "status",
            "state",
            "warn",
            "warning",
            "sperr",
            "lock",
            "trip",
            "druck",
            "pressure",
            "temperatur",
            "vorlauf",
            "ruecklauf",
            "rücklauf",
        ],
        question_keywords=[
            "auffaellig",
            "auffällig",
            "fehler",
            "fehlercode",
            "alarm",
            "stoer",
            "stör",
            "warnung",
            "stoerung",
            "störung",
        ],
        fallback_entity_limit=14,
    ),
    "health": IntentEntityProfile(
        intent="health",
        entity_keywords=[
            "status",
            "betrieb",
            "state",
            "error",
            "fault",
            "alarm",
            "temperatur",
            "vorlauf",
            "ruecklauf",
            "rücklauf",
            "durchfluss",
            "flow",
            "druck",
            "pressure",
        ],
        question_keywords=["normal", "ok", "gesund", "zustand", "status"],
        fallback_entity_limit=10,
    ),
    "general": IntentEntityProfile(
        intent="general",
        entity_keywords=[
            "status",
            "betrieb",
            "state",
            "temperatur",
            "vorlauf",
            "ruecklauf",
            "rücklauf",
            "durchfluss",
            "flow",
            "fehler",
            "error",
            "fault",
            "alarm",
            "code",
            "warn",
        ],
        question_keywords=["analyse", "auffaellig", "auffällig", "normal", "zustand", "status"],
        fallback_entity_limit=10,
    ),
}


def get_intent_profile(intent: str) -> IntentEntityProfile:
    return INTENT_ENTITY_PROFILES.get(intent, INTENT_ENTITY_PROFILES["general"])


MANUFACTURER_INTENT_ALIASES: Dict[str, Dict[str, List[str]]] = {
    "vaillant": {
        "flow": ["pc0", "pc1", "vfs", "vol_flow"],
        "hot_water": ["dhw", "sp_tank", "warmwasser"],
        "cycling": ["compressor_starts", "verdichter_start"],
    },
    "stiebel": {
        "flow": ["hk1_flow", "hk2_flow", "volumenstrom"],
        "hot_water": ["ww", "ww_temp", "speicher"],
        "cycling": ["verdichter", "kompressor", "starts"],
    },
    "nibe": {
        "flow": ["bt2", "gp1", "flow", "volumenstrom"],
        "hot_water": ["bt6", "dhw", "warmwasser"],
        "cycling": ["compressor", "status", "runtime"],
    },
}


def get_manufacturer_aliases(manufacturer: Optional[str], intent: str) -> List[str]:
    if not manufacturer:
        return []
    key = manufacturer.strip().lower()
    alias_map = MANUFACTURER_INTENT_ALIASES.get(key, {})
    return alias_map.get(intent, [])


# Optionales Mapping technischer Begriffe auf lesbare Namen.
FRIENDLY_ENTITY_HINTS: Dict[str, str] = {
    "pc0": "Durchflusskreis PC0",
    "pc1": "Durchflusskreis PC1",
    "vorlauf": "Vorlauftemperatur",
    "ruecklauf": "Ruecklauftemperatur",
    "rücklauf": "Ruecklauftemperatur",
    "warmwasser": "Warmwasser",
    "dhw": "Warmwasser",
    "verdichter": "Verdichterstatus",
}
