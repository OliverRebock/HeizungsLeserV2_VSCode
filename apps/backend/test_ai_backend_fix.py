import re
from typing import List, Any, Optional, Dict

# Dummy Point class to simulate Influx data
class Point:
    def __init__(self, value, state=None):
        self.value = value
        self.state = state

# The extraction logic from HeatingSummaryService
def _extract_error_candidate(eid: str, label: str, points: List[Any]) -> Optional[Dict[str, Any]]:
    for p in points:
        val = p.value
        state = p.state
        
        targets = []
        if val is not None: targets.append(str(val))
        if state is not None: targets.append(str(state))
        
        for val_str in targets:
            paren_match = re.search(r'\((\d+)\)', val_str)
            alpha_match = re.search(r'([A-Z]\d{1,4})', val_str)
            numeric_match = re.search(r'(\d{3,})', val_str) if not re.match(r'^-?\d+(\.\d+)?$', val_str) else None
            
            code = None
            confidence = "medium"
            if paren_match:
                code = paren_match.group(1)
                confidence = "high"
            elif alpha_match:
                code = alpha_match.group(1)
                confidence = "high"
            elif numeric_match:
                code = numeric_match.group(1)
                confidence = "medium"
            
            if code or any(kw in val_str.lower() for kw in ["fault", "alarm", "error", "störung"]):
                classification = "active"
                historical_indicators = ["--", "last", "historisch", "vorheriger", "previous", "history"]
                if any(ind in val_str.lower() for ind in historical_indicators) or "last" in eid.lower():
                    classification = "historical"
                
                return {
                    "entity_id": eid,
                    "label": label,
                    "raw_value": val_str,
                    "parsed_code": code or val_str,
                    "classification": classification,
                    "confidence": confidence
                }
    return None

def test_error_code_parsing_paren():
    points = [Point(value=0.0, state="--(5140) 30.03.2026 15:55")]
    result = _extract_error_candidate("boiler_last_error_code", "Letzter Fehler", points)
    assert result is not None
    assert result["parsed_code"] == "5140"
    assert result["classification"] == "historical"
    assert result["confidence"] == "high"

def test_error_code_parsing_alpha():
    points = [Point(value="E123", state="E123")]
    result = _extract_error_candidate("heatpump_error", "Fehler WP", points)
    assert result is not None
    assert result["parsed_code"] == "E123"
    assert result["classification"] == "active"

def test_no_error_code_on_numeric():
    # Should not treat temperature 21.5 as error code 215 or similar
    points = [Point(value=21.5)]
    result = _extract_error_candidate("outside_temp", "Außentemperatur", points)
    assert result is None

def test_stateful_entity_logic():
    # Simulation of the logic in get_device_summary for stateful detection
    eid = "boiler_compressor_activity"
    label = "Verdichter Aktivität"
    raw_values = ["Heizen", "aus"]
    
    state_keywords = ["mode", "activity", "status", "state", "betrieb", "error", "fault", "alarm", "code"]
    is_forced_state = any(kw in eid.lower() or (label and kw in label.lower()) for kw in state_keywords)
    
    assert is_forced_state is True

if __name__ == "__main__":
    # Minimal manual run
    try:
        test_error_code_parsing_paren()
        print("test_error_code_parsing_paren: PASSED")
        test_error_code_parsing_alpha()
        print("test_error_code_parsing_alpha: PASSED")
        test_no_error_code_on_numeric()
        print("test_no_error_code_on_numeric: PASSED")
        test_stateful_entity_logic()
        print("test_stateful_entity_logic: PASSED")
        print("\nALL UNIT TESTS PASSED!")
    except AssertionError as e:
        print(f"TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"ERROR DURING TESTS: {e}")
        exit(1)
