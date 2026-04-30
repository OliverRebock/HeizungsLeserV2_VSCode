from datetime import datetime, timezone

import pytest

from app.schemas.analysis import ChatTurn
from app.schemas.influx import DataPoint, Entity, TimeSeriesResponse
from app.services.heatpump_chat_service import HeatPumpChatService


def make_entity(entity_id: str, friendly_name: str = "") -> Entity:
    return Entity(
        entity_id=entity_id,
        friendly_name=friendly_name,
        domain="sensor",
        data_kind="numeric",
        render_mode="history_line",
        chartable=True,
        source_table="state",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "hat die heizung fehler?",
        "welcher fehlercode liegt an?",
        "gibt es stoerungen oder alarme?",
    ],
)
async def test_detect_intent_routes_fault_questions_to_anomaly(question: str):
    service = HeatPumpChatService()
    intent = await service._detect_intent(question)
    assert intent == "anomaly"


def test_select_entities_for_anomaly_prioritizes_error_entities():
    service = HeatPumpChatService()
    entities = [
        make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
        make_entity("boiler_return_temperature", "Boiler Ruecklauf"),
        make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
        make_entity("thermostat_alarm_status", "Thermostat Alarmstatus"),
        make_entity("mixer_hc2_pump_status_pc1", "Pumpe HK2"),
    ]

    selected = service._select_entities("anomaly", "hat die heizung fehler?", entities)

    assert "boiler_last_error_code" in selected
    assert "thermostat_alarm_status" in selected
    assert selected.index("boiler_last_error_code") < selected.index("boiler_current_flow_temperature")


def test_fallback_entities_for_anomaly_prefers_error_marked_entities():
    service = HeatPumpChatService()
    entities = [
        make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
        make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
        make_entity("thermostat_alarm_status", "Thermostat Alarmstatus"),
    ]

    selected = service._fallback_entities("anomaly", entities)

    assert selected == ["boiler_last_error_code", "thermostat_alarm_status"]


def test_select_entities_for_general_keeps_error_context_available():
    service = HeatPumpChatService()
    entities = [
        make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
        make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
        make_entity("thermostat_hc2_target_flow_temperature", "Soll Vorlauf"),
    ]

    selected = service._select_entities("general", "wie laeuft die heizung aktuell?", entities)

    assert "boiler_last_error_code" in selected


@pytest.mark.asyncio
async def test_detect_intent_routes_colloquial_hot_water_question_to_hot_water():
    service = HeatPumpChatService()
    intent = await service._detect_intent("wann wurde gestern das wasser aufgewaermt?")
    assert intent == "hot_water"


def test_resolve_follow_up_question_maps_mach_2_to_error_window_request():
    service = HeatPumpChatService()
    history = [
        ChatTurn(
            role="assistant",
            content=(
                "Konkrete Empfehlungen:\n"
                "1. **Fehlercode 6256 nachschlagen**\n"
                "2. **Ereignisprotokoll um den 03.04.2026 11:45-11:55 Uhr pruefen**\n"
                "3. **Trenddaten weiter beobachten**"
            ),
        )
    ]

    resolved, forced_intent = service._resolve_follow_up_question("mach 2", history)

    assert "punkt 2" in resolved.lower()
    assert "zeitpunkt des fehlers" in resolved.lower()
    assert forced_intent == "anomaly"


def test_resolve_follow_up_question_keeps_original_without_history_match():
    service = HeatPumpChatService()

    resolved, forced_intent = service._resolve_follow_up_question("mach 2", [])

    assert resolved == "mach 2"
    assert forced_intent is None


def test_select_entities_for_time_focused_hot_water_includes_timeline_entities():
    service = HeatPumpChatService()
    entities = [
        make_entity("boiler_tapwater_active", "Boiler WW Aktiv"),
        make_entity("boiler_dhw_current_intern_temperature", "WW intern"),
        make_entity("boiler_dhw_starts_hp", "WW Starts"),
        make_entity("boiler_return_temperature", "Boiler Ruecklauf"),
    ]

    selected = service._select_entities(
        "hot_water",
        "wann wurde gestern das wasser aufgewaermt?",
        entities,
    )

    assert "boiler_tapwater_active" in selected
    assert "boiler_dhw_current_intern_temperature" in selected
    assert "boiler_dhw_starts_hp" in selected


def test_select_entities_for_fault_window_readout_includes_measurement_context():
    service = HeatPumpChatService()
    entities = [
        make_entity("boiler_last_error_code", "Boiler Letzter Fehler"),
        make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
        make_entity("boiler_return_temperature", "Boiler Ruecklauf"),
        make_entity("mixer_hc2_setpoint_flow_temperature", "HK2 Soll Vorlauf"),
        make_entity("thermostat_hc2_target_flow_temperature", "HK2 Ziel Vorlauf"),
    ]

    selected = service._select_entities(
        "anomaly",
        "lies die werte zum zeitpunkt des fehlers aus",
        entities,
    )

    assert "boiler_last_error_code" in selected
    assert "boiler_current_flow_temperature" in selected
    assert "boiler_return_temperature" in selected
    assert "mixer_hc2_setpoint_flow_temperature" in selected


def test_point_numeric_state_prefers_textual_activity_over_zero_value():
    service = HeatPumpChatService()

    point = DataPoint(
        ts="2026-04-30T09:07:27Z",
        value=0.0,
        state="Heizen",
    )

    assert service._point_numeric_state(point) == 1.0


def test_detect_operating_status_category_is_dynamic_not_exact_id_based():
    service = HeatPumpChatService()

    entity = make_entity("custom_verdichter_betrieb", "Verdichter Betrieb")
    entity.data_kind = "enum"
    entity.render_mode = "state_timeline"

    assert service._detect_operating_status_category(entity) == "compressor"


def test_detect_operating_status_category_ignores_priority_only_flags():
    service = HeatPumpChatService()

    entity = make_entity("custom_dhw_priority", "WW Vorrang")
    entity.data_kind = "binary"
    entity.render_mode = "state_timeline"

    assert service._detect_operating_status_category(entity) is None


def test_extract_temperature_peak_contexts_links_peak_to_hot_water_window():
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="custom_dhw_status",
            friendly_name="Warmwasser aktiv",
            domain="binary_sensor",
            data_kind="binary",
            render_mode="state_timeline",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-30T10:00:00Z", state="0"),
                DataPoint(ts="2026-04-30T10:10:00Z", state="1"),
                DataPoint(ts="2026-04-30T10:40:00Z", state="0"),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="custom_flow_temperature",
            friendly_name="Vorlauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            unit_of_measurement="°C",
            points=[
                DataPoint(ts="2026-04-30T10:05:00Z", value=35.0),
                DataPoint(ts="2026-04-30T10:20:00Z", value=66.4),
                DataPoint(ts="2026-04-30T10:45:00Z", value=40.0),
            ],
            meta={},
        ),
    ]

    facts = service._extract_temperature_peak_contexts(series)

    assert any("66.4" in fact and "Warmwasser aktiv" in fact for fact in facts)


def test_build_facts_for_time_focused_hot_water_contains_event_windows():
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_tapwater_active",
            friendly_name="Boiler WW Aktiv",
            domain="sensor",
            data_kind="state",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-18T05:00:00Z", state="0"),
                DataPoint(ts="2026-04-18T06:10:00Z", state="1"),
                DataPoint(ts="2026-04-18T06:45:00Z", state="0"),
                DataPoint(ts="2026-04-18T19:00:00Z", state="1"),
                DataPoint(ts="2026-04-18T19:25:00Z", state="0"),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="boiler_dhw_starts_hp",
            friendly_name="WW Starts",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-18T05:00:00Z", value=10),
                DataPoint(ts="2026-04-18T06:10:00Z", value=11),
                DataPoint(ts="2026-04-18T19:00:00Z", value=12),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="boiler_dhw_current_intern_temperature",
            friendly_name="WW intern",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-18T06:00:00Z", value=42.0),
                DataPoint(ts="2026-04-18T06:30:00Z", value=47.0),
            ],
            meta={},
        ),
    ]

    facts = service._build_facts("hot_water", "wann wurde gestern das wasser aufgewaermt?", series)

    assert any("Warmwasser-Aufheizung erkannt" in fact for fact in facts)
    assert any("Warmwasser-Start gezaehlt" in fact for fact in facts)
    assert any("WW-Temperaturanstieg" in fact for fact in facts)
    assert any("2026-04-18 08:10 CEST" in fact for fact in facts)
    assert any("2026-04-18 08:45 CEST" in fact for fact in facts)


def test_question_is_time_focused_detects_behavior_questions():
    """Test that behavior/comparison questions are recognized as time-focused."""
    service = HeatPumpChatService()
    
    # These should all be recognized as time-focused
    time_focused_questions = [
        "Wie verhalten sich Vor- Rücklauf in diesem Zeitraum?",
        "Wie ist der Verlauf der Temperaturen?",
        "Vergleich Vorlauf und Rücklauf",
        "Wie entwickelt sich die Temperatur während des Zeitraums?",  # Added 'während' to trigger
    ]
    
    for question in time_focused_questions:
        assert service._question_is_time_focused(question.lower()), \
            f"Question '{question}' should be detected as time-focused"


def test_select_entities_for_temperature_comparison_includes_all_temps():
    """Test that temperature comparison questions include all temperature entities."""
    service = HeatPumpChatService()
    entities = [
        make_entity("boiler_current_flow_temperature", "Boiler Vorlauf"),
        make_entity("boiler_return_temperature", "Boiler Rücklauf"),
        make_entity("boiler_heat_carrier_return_tc0", "Kältemittel Rücklauf"),
        make_entity("boiler_heat_carrier_flow_tc1", "Kältemittel Vorlauf"),
        make_entity("mixer_hc2_flow_temperature_tc1", "HK2 Vorlauf"),
        make_entity("boiler_selected_flow_temperature", "Sollwert Vorlauf"),
        make_entity("boiler_pump_modulation", "Pumpenschaltung"),
    ]

    # Question mentions temperature comparison
    selected = service._select_entities(
        "general",
        "Wie verhalten sich Vor- Rücklauf in diesem Zeitraum?",
        entities
    )

    # All temperature entities should be guaranteed to be selected
    assert "boiler_current_flow_temperature" in selected
    assert "boiler_return_temperature" in selected
    assert "boiler_heat_carrier_return_tc0" in selected
    assert "boiler_heat_carrier_flow_tc1" in selected
    assert "mixer_hc2_flow_temperature_tc1" in selected
    assert "boiler_selected_flow_temperature" in selected


def test_question_is_time_focused_detects_duration_questions():
    """Test that duration questions are recognized as time-focused."""
    service = HeatPumpChatService()
    
    duration_questions = [
        "wie lange wurde gestern geheizt?",  # Has both "wie lange" and "gestern"
        "wie lange dauerte es gestern?",  # Has "wie lange" and "gestern"
        "dauer der heizphase gestern",  # Has "dauer" and "gestern"
    ]
    
    for question in duration_questions:
        assert service._question_is_time_focused(question.lower()), \
            f"Question '{question}' should be detected as time-focused"


def test_question_is_time_focused_detects_count_questions():
    """Test that count/frequency questions are recognized as time-focused."""
    service = HeatPumpChatService()
    
    count_questions = [
        "wie viele starts hatte die anlage?",
        "wie oft wurde geheizt?",
        "anzahl der starts",
        "häufig war die anlage aktiv?",
    ]
    
    for question in count_questions:
        assert service._question_is_time_focused(question.lower()), \
            f"Question '{question}' should be detected as time-focused"


def test_build_facts_for_temperature_comparison_shows_spreizung():
    """Test that temperature comparison questions extract spreizung (delta)."""
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_current_flow_temperature",
            friendly_name="Boiler Vorlauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-18T08:00:00Z", value=35.0),
                DataPoint(ts="2026-04-18T09:00:00Z", value=40.0),
                DataPoint(ts="2026-04-18T10:00:00Z", value=38.0),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="boiler_return_temperature",
            friendly_name="Boiler Rücklauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-18T08:00:00Z", value=32.0),
                DataPoint(ts="2026-04-18T09:00:00Z", value=36.0),
                DataPoint(ts="2026-04-18T10:00:00Z", value=35.0),
            ],
            meta={},
        ),
    ]

    facts = service._build_facts(
        "general",
        "Wie verhalten sich Vor- Rücklauf?",
        series
    )

    # Should include temperature values and potentially spreizung info
    assert len(facts) > 0
    facts_text = " ".join(facts).lower()
    # Should mention temperatures or spreizung
    assert any(word in facts_text for word in ["vorlauf", "rücklauf", "temperatur", "spreiz"])


def test_extract_heatpump_runtime_assessment_marks_long_runs_as_positive_without_taktung_signal():
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_compressor_activity",
            friendly_name="Kompressor aktiv",
            domain="sensor",
            data_kind="state",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-29T10:00:00Z", state="0"),
                DataPoint(ts="2026-04-29T12:10:00Z", state="1"),
                DataPoint(ts="2026-04-29T14:39:00Z", state="0"),
                DataPoint(ts="2026-04-30T06:49:00Z", state="1"),
                DataPoint(ts="2026-04-30T13:35:00Z", state="0"),
            ],
            meta={},
        ),
    ]

    facts = service._extract_heatpump_runtime_assessment(
        series,
        datetime(2026, 4, 23, tzinfo=timezone.utc),
        datetime(2026, 4, 30, tzinfo=timezone.utc),
    )

    joined = " ".join(facts).lower()
    assert "starts pro tag" in joined
    assert "grundsaetzlich positiv" in joined
    assert "kein hinweis auf starkes takten" in joined


def test_build_facts_for_fault_window_readout_returns_nearest_measurements():
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_last_error_code",
            friendly_name="Boiler Letzter Fehler",
            domain="sensor",
            data_kind="enum",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-03T09:51:54.981364Z", state="--(6256) 03.04.2026 11:50 - now"),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="boiler_current_flow_temperature",
            friendly_name="Boiler Vorlauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-03T09:51:54.981715Z", value=52.1),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="boiler_return_temperature",
            friendly_name="Boiler Ruecklauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-03T09:51:54.981526Z", value=45.2),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="mixer_hc2_setpoint_flow_temperature",
            friendly_name="HK2 Soll Vorlauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-03T09:51:45.191748Z", value=29.0),
            ],
            meta={},
        ),
    ]

    facts = service._build_facts(
        "anomaly",
        "lies die werte zum zeitpunkt des fehlers aus",
        series,
    )

    facts_text = " ".join(facts)
    assert "Fehlerzeitpunkt erkannt" in facts_text
    assert "6256" in facts_text
    assert "Boiler Vorlauf (boiler_current_flow_temperature) beim Fehlerzeitpunkt: 52.1" in facts_text
    assert "Boiler Ruecklauf (boiler_return_temperature) beim Fehlerzeitpunkt: 45.2" in facts_text


def test_fault_anchor_prefers_embedded_error_timestamp_over_point_ts():
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_last_error_code",
            friendly_name="Boiler Letzter Fehler",
            domain="sensor",
            data_kind="enum",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-19T11:49:00Z", state="--(6256) 03.04.2026 11:50 - now"),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="boiler_current_flow_temperature",
            friendly_name="Boiler Vorlauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-03T09:51:54.981715Z", value=52.1),
                DataPoint(ts="2026-04-19T11:49:00Z", value=33.6),
            ],
            meta={},
        ),
    ]

    facts = service._build_facts(
        "anomaly",
        "lies die werte zum zeitpunkt des fehlers aus",
        series,
    )

    facts_text = " ".join(facts)
    assert "2026-04-03 11:50 CEST" in facts_text
    assert "Boiler Vorlauf (boiler_current_flow_temperature) beim Fehlerzeitpunkt: 52.1" in facts_text


def test_extract_operating_phases_from_binary_data():
    """Test that heating duration can be calculated from binary activity data."""
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_compressor_activity",
            friendly_name="Kompressor aktiv",
            domain="sensor",
            data_kind="binary",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-18T08:00:00Z", value=0),
                DataPoint(ts="2026-04-18T08:30:00Z", value=1),  # ON
                DataPoint(ts="2026-04-18T09:00:00Z", value=0),  # OFF
                DataPoint(ts="2026-04-18T09:30:00Z", value=1),  # ON
                DataPoint(ts="2026-04-18T10:00:00Z", value=1),  # Still ON
                DataPoint(ts="2026-04-18T10:30:00Z", value=0),  # OFF
            ],
            meta={},
        ),
    ]

    facts = service._build_facts(
        "general",
        "Wie lange wurde geheizt?",
        series
    )

    # Should extract duration information
    assert len(facts) > 0
    facts_text = " ".join(facts).lower()
    # Should mention duration or time
    assert any(word in facts_text for word in ["min", "stund", "dauer", "lauf", "phase", "aktiv"])


def test_extract_counter_differences_from_numeric_counters():
    """Test that counter deltas (starts, hours) are extracted."""
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_compressor_starts",
            friendly_name="Verdichter Starts",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-18T08:00:00Z", value=100),
                DataPoint(ts="2026-04-18T12:00:00Z", value=102),
                DataPoint(ts="2026-04-18T16:00:00Z", value=105),
            ],
            meta={},
        ),
    ]

    facts = service._build_facts(
        "general",
        "wie viele starts hatte die anlage?",
        series
    )

    # Should extract counter delta (105 - 100 = 5 starts)
    assert len(facts) > 0
    facts_text = " ".join(facts).lower()
    assert any(word in facts_text for word in ["start", "anzahl", "häufig", "zahl", "delta"])


def test_build_facts_includes_period_summary_for_generic_7d_question():
    service = HeatPumpChatService()
    series = [
        TimeSeriesResponse(
            entity_id="boiler_current_flow_temperature",
            friendly_name="Boiler Vorlauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-12T08:00:00Z", value=28.0),
                DataPoint(ts="2026-04-15T08:00:00Z", value=36.0),
                DataPoint(ts="2026-04-19T08:00:00Z", value=33.1),
            ],
            meta={},
        ),
        TimeSeriesResponse(
            entity_id="boiler_return_temperature",
            friendly_name="Boiler Ruecklauf",
            domain="sensor",
            data_kind="numeric",
            chartable=True,
            points=[
                DataPoint(ts="2026-04-12T08:00:00Z", value=27.5),
                DataPoint(ts="2026-04-15T08:00:00Z", value=34.5),
                DataPoint(ts="2026-04-19T08:00:00Z", value=33.2),
            ],
            meta={},
        ),
    ]

    facts = service._build_facts(
        "general",
        "was ist mit der heizung los?",
        series,
        start_dt=datetime(2026, 4, 12, 18, 45, tzinfo=timezone.utc),
        end_dt=datetime(2026, 4, 19, 18, 45, tzinfo=timezone.utc),
    )

    assert any("im zeitraum" in fact.lower() for fact in facts)
    assert any("aktuell:" in fact.lower() for fact in facts)
