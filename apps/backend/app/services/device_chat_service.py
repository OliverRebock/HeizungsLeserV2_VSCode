from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Tuple

from app.models.device import Device
from app.schemas.analysis import (
    ChatTurn,
    DeviceChatHistoryResponse,
    DeviceChatMessage,
    DeviceChatRequest,
    DeviceChatResponse,
    HeatPumpChatRequest,
)
from app.services.heatpump_chat_service import heatpump_chat_service


class DeviceChatHistoryStore:
    def __init__(self, max_items: int = 100) -> None:
        self.max_items = max_items
        self._store: Dict[Tuple[int, int], Deque[DeviceChatMessage]] = defaultdict(lambda: deque(maxlen=self.max_items))

    def get(self, user_id: int, device_id: int, limit: int = 30) -> List[DeviceChatMessage]:
        key = (user_id, device_id)
        items = list(self._store.get(key, deque()))
        if limit <= 0:
            return items
        return items[-limit:]

    def append(self, user_id: int, device_id: int, message: DeviceChatMessage) -> None:
        key = (user_id, device_id)
        self._store[key].append(message)


class DeviceChatService:
    def __init__(self) -> None:
        self.history = DeviceChatHistoryStore(max_items=120)

    def _to_chat_turns(self, messages: List[DeviceChatMessage]) -> List[ChatTurn]:
        turns: List[ChatTurn] = []
        for message in messages:
            turns.append(ChatTurn(role=message.role, content=message.content))
        return turns

    def _build_chart_suggestions(self, entity_ids: List[str]) -> List[str]:
        suggestions: List[str] = []
        lowered = [entity.lower() for entity in entity_ids]

        has_flow = any("flow" in entity or "durchfluss" in entity for entity in lowered)
        has_temp = any(
            marker in entity
            for marker in ["temperature", "temperatur", "vorlauf", "ruecklauf", "r\u00fccklauf", "outside"]
            for entity in lowered
        )
        has_power = any(
            marker in entity
            for marker in ["power", "leistung", "modulation", "compressor"]
            for entity in lowered
        )
        has_fault = any(
            marker in entity
            for marker in ["fault", "error", "fehler", "alarm", "code"]
            for entity in lowered
        )

        if has_temp:
            suggestions.append("Vorlauf, Ruecklauf und Aussentemperatur im Zeitverlauf vergleichen")
        if has_flow:
            suggestions.append("Durchflusswerte von PC0/PC1 als Verlauf anzeigen")
        if has_power:
            suggestions.append("Verdichterleistung und Modulation gemeinsam visualisieren")
        if has_fault:
            suggestions.append("Fehlerstatus und relevante Prozesswerte rund um den Fehlerzeitpunkt vergleichen")

        if not suggestions:
            suggestions.append("Relevante Entitaeten als Vergleichsdiagramm anzeigen")

        return suggestions[:3]

    def _build_uncertainty(self, evidence: List[str]) -> str | None:
        joined = " ".join(evidence).lower()
        indicators = [
            "keine passenden messwerte",
            "keine messwerte",
            "keine daten",
            "nicht gefunden",
            "nicht sicher",
        ]
        if any(indicator in joined for indicator in indicators):
            return "Die Datenlage ist eingeschraenkt; fuer eine sichere Aussage sind weitere passende Messwerte notwendig."
        return None

    async def ask(
        self,
        device: Device,
        user_id: int,
        request: DeviceChatRequest,
    ) -> DeviceChatResponse:
        server_history = self.history.get(user_id, device.id, limit=max(2, min(request.max_history_turns * 2, 60)))
        turns_from_server = self._to_chat_turns(server_history) if request.use_server_history else []

        merged_history = [*turns_from_server, *request.history]
        if request.max_history_turns > 0:
            merged_history = merged_history[-request.max_history_turns:]

        hp_request = HeatPumpChatRequest(
            question=request.question,
            start=request.start,
            end=request.end,
            language=request.language,
            history=merged_history,
            entity_ids=request.selected_entity_ids,
        )

        result = await heatpump_chat_service.answer_question(device, hp_request)

        now = datetime.now(timezone.utc)
        self.history.append(
            user_id,
            device.id,
            DeviceChatMessage(role="user", content=request.question, created_at=now),
        )
        self.history.append(
            user_id,
            device.id,
            DeviceChatMessage(
                role="assistant",
                content=result.answer,
                created_at=now,
                detected_intent=result.intent,
                resolved_entities=result.used_entity_ids,
                used_time_range=result.timeframe,
            ),
        )

        uncertainty = self._build_uncertainty(result.evidence)

        return DeviceChatResponse(
            answer=result.answer,
            detected_intent=result.intent,
            resolved_entities=result.used_entity_ids,
            used_time_range=result.timeframe,
            evidence=result.evidence,
            confidence="medium" if uncertainty else "high",
            uncertainty=uncertainty,
            chart_suggestions=self._build_chart_suggestions(result.used_entity_ids),
            disclaimer=result.disclaimer,
        )

    def get_history(self, user_id: int, device_id: int, limit: int = 30) -> DeviceChatHistoryResponse:
        history = self.history.get(user_id, device_id, limit=limit)
        return DeviceChatHistoryResponse(device_id=device_id, history=history)


device_chat_service = DeviceChatService()
