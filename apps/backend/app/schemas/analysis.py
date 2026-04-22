from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class AnalysisRequest(BaseModel):
    start: Optional[datetime] = Field(None, alias="from")
    end: Optional[datetime] = Field(None, alias="to")
    entity_ids: Optional[List[str]] = Field(default_factory=list)
    analysis_focus: Optional[str] = "Gesamtzustand, Effizienz und Taktung"
    language: str = "de"
    include_raw_summary: bool = False
    
    # New fields for deep analysis context
    manufacturer: Optional[str] = None
    heat_pump_type: Optional[str] = None

    class Config:
        populate_by_name = True


class ChatTurn(BaseModel):
    role: str  # user | assistant
    content: str


class HeatPumpChatRequest(BaseModel):
    question: str
    start: Optional[datetime] = Field(None, alias="from")
    end: Optional[datetime] = Field(None, alias="to")
    language: str = "de"
    history: List[ChatTurn] = Field(default_factory=list)
    entity_ids: List[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class HeatPumpChatResponse(BaseModel):
    intent: str
    answer: str
    used_entity_ids: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    timeframe: Dict[str, str]
    disclaimer: str = "Die Antwort ist eine datenbasierte KI-Einschaetzung und ersetzt keine fachliche Vor-Ort-Pruefung."


class DeviceChatRequest(BaseModel):
    question: str
    start: Optional[datetime] = Field(None, alias="from")
    end: Optional[datetime] = Field(None, alias="to")
    language: str = "de"
    selected_entity_ids: List[str] = Field(default_factory=list)
    history: List[ChatTurn] = Field(default_factory=list)
    use_server_history: bool = True
    max_history_turns: int = 10

    class Config:
        populate_by_name = True


class DeviceChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    detected_intent: Optional[str] = None
    resolved_entities: List[str] = Field(default_factory=list)
    used_time_range: Optional[Dict[str, str]] = None


class DeviceChatResponse(BaseModel):
    answer: str
    detected_intent: str
    resolved_entities: List[str] = Field(default_factory=list)
    used_time_range: Dict[str, str]
    evidence: List[str] = Field(default_factory=list)
    confidence: str = "medium"
    uncertainty: Optional[str] = None
    chart_suggestions: List[str] = Field(default_factory=list)
    disclaimer: str = "Die Antwort ist eine datenbasierte KI-Einschaetzung und ersetzt keine fachliche Vor-Ort-Pruefung."


class DeviceChatHistoryResponse(BaseModel):
    device_id: int
    history: List[DeviceChatMessage] = Field(default_factory=list)

class Finding(BaseModel):
    title: str
    severity: str  # low, medium, high, critical
    description: str
    evidence: List[str] = Field(default_factory=list)

class Anomaly(BaseModel):
    title: str
    description: str

class DetectedErrorCode(BaseModel):
    code: str
    label: str
    source_entity: str
    source_label: str
    observed_value: str
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    seen_count: int = 1

class DeepAnalysisResponse(BaseModel):
    device_id: int
    device_name: str
    start: datetime = Field(..., alias="from")
    end: datetime = Field(..., alias="to")
    technical_summary: str
    diagnostic_steps: List[str] = Field(default_factory=list)
    suspected_causes: List[str] = Field(default_factory=list)
    technical_findings: List[Finding] = Field(default_factory=list)
    confidence: str = "medium"
    analysis_mode: str = "ai"
    analysis_notice: Optional[str] = None
    disclaimer: str = "Diese vertiefte Analyse ist eine technische KI-Einschätzung und ersetzt keine professionelle Fehlerdiagnose vor Ort."

    class Config:
        populate_by_name = True

class ErrorCandidate(BaseModel):
    entity_id: str
    label: str
    raw_value: str
    parsed_code: Optional[str] = None
    classification: str = "unknown"  # historical, active, unknown
    confidence: str = "medium"
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    seen_count: int = 1

class AnalysisResponse(BaseModel):
    device_id: int
    device_name: str
    start: datetime = Field(..., alias="from")
    end: datetime = Field(..., alias="to")
    summary: str
    overall_status: str
    findings: List[Finding] = Field(default_factory=list)
    anomalies: List[Anomaly] = Field(default_factory=list)
    optimization_hints: List[str] = Field(default_factory=list)
    detected_error_codes: List[DetectedErrorCode] = Field(default_factory=list)
    error_candidates: List[ErrorCandidate] = Field(default_factory=list)
    recommended_followup_checks: List[str] = Field(default_factory=list)
    confidence: str = "medium"
    should_trigger_error_analysis: bool = False
    analysis_mode: str = "ai"
    analysis_notice: Optional[str] = None
    disclaimer: str = "Die Analyse ist eine datenbasierte KI-Einschätzung und ersetzt keine fachliche Vor-Ort-Prüfung."
    raw_summary: Optional[Any] = None
    deep_analysis_result: Optional[DeepAnalysisResponse] = None
    analysis_run_id: Optional[str] = None

    class Config:
        populate_by_name = True
