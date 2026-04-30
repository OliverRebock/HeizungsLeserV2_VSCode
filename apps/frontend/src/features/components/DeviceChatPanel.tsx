import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MessageSquareText, Send, Loader2, RefreshCw, Trash2, Clock } from 'lucide-react';
import api from '../../lib/api';
import MarkdownMessage from '../../components/MarkdownMessage';
import type {
  DeviceChatHistoryResponse,
  DeviceChatMessage,
  DeviceChatRequest,
  DeviceChatResponse,
  Entity,
} from '../../types/api';

type DeviceChatPanelProps = {
  deviceId: string;
};

const CHAT_RANGES = [
  { label: 'Letzte 24h', value: '24h' },
  { label: 'Letzte 7 Tage', value: '7d' },
  { label: 'Letzte 30 Tage', value: '30d' },
];

const getRangeStart = (range: string): Date => {
  const d = new Date();
  if (range === '24h') d.setHours(d.getHours() - 24);
  else if (range === '7d') d.setDate(d.getDate() - 7);
  else if (range === '30d') d.setDate(d.getDate() - 30);
  return d;
};

const QUICK_PROMPTS = [
  'Gab es auffällige Betriebszustände im gewählten Zeitraum?',
  'Wie verhalten sich Vorlauf, Rücklauf und Außentemperatur?',
  'Gibt es Hinweise auf Takten oder ungünstige Modulation?',
  'Welche Messwerte sollte ich als nächstes im Verlauf prüfen?',
];

const DeviceChatPanel: React.FC<DeviceChatPanelProps> = ({ deviceId }) => {
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<DeviceChatMessage[]>([]);
  const [selectedEntityIds, setSelectedEntityIds] = useState<string[]>([]);
  const [selectedRange, setSelectedRange] = useState<string>('24h');
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: entities } = useQuery({
    queryKey: ['device-chat-entities', deviceId],
    queryFn: async () => {
      const response = await api.get<Entity[]>(`/data/${deviceId}/entities`);
      return response.data;
    },
    enabled: !!deviceId,
  });

  const { data: history, isLoading: isHistoryLoading, refetch } = useQuery({
    queryKey: ['device-chat-history', deviceId],
    queryFn: async () => {
      const response = await api.get<DeviceChatHistoryResponse>(`/chat/device/${deviceId}/history`, {
        params: { limit: 40 },
      });
      return response.data;
    },
    enabled: !!deviceId,
  });

  useEffect(() => {
    setMessages(history?.history || []);
  }, [history]);

  const candidateEntities = useMemo(() => {
    if (!entities) return [];
    return entities
      .filter((entity) => entity.chartable || entity.domain === 'sensor' || entity.domain === 'binary_sensor')
      .slice(0, 30);
  }, [entities]);

  const sendMutation = useMutation({
    mutationFn: async (payload: DeviceChatRequest) => {
      const response = await api.post<DeviceChatResponse>(`/chat/device/${deviceId}`, payload);
      return response.data;
    },
    onSuccess: (data) => {
      const nowIso = new Date().toISOString();
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          created_at: nowIso,
          detected_intent: data.detected_intent,
          resolved_entities: data.resolved_entities,
          used_time_range: data.used_time_range,
        },
      ]);
      queryClient.invalidateQueries({ queryKey: ['device-chat-history', deviceId] });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sendMutation.isPending]);

  const clearMutation = useMutation({
    mutationFn: async () => {
      await api.delete(`/chat/device/${deviceId}/history`);
    },
    onSuccess: () => {
      setMessages([]);
      queryClient.invalidateQueries({ queryKey: ['device-chat-history', deviceId] });
    },
  });

  const submitQuestion = (rawQuestion?: string) => {
    const trimmed = (rawQuestion ?? question).trim();
    if (!trimmed || sendMutation.isPending) return;

    const nowIso = new Date().toISOString();
    setMessages((prev) => [...prev, { role: 'user', content: trimmed, created_at: nowIso }]);
    setQuestion('');

    const rangeStart = getRangeStart(selectedRange);
    const rangeEnd = new Date();

    sendMutation.mutate({
      question: trimmed,
      language: 'de',
      selected_entity_ids: selectedEntityIds,
      use_server_history: true,
      max_history_turns: 12,
      from: rangeStart.toISOString(),
      to: rangeEnd.toISOString(),
    });
  };

  const toggleEntity = (entityId: string) => {
    setSelectedEntityIds((prev) =>
      prev.includes(entityId) ? prev.filter((id) => id !== entityId) : [...prev, entityId],
    );
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <MessageSquareText className="w-5 h-5 text-blue-600" />
              KI-Einsatz-Chat
            </h3>
            <p className="text-sm text-slate-500">
              Stellt technische Fragen zum aktuellen Gerät. Antworten basieren auf den vorhandenen Messdaten.
            </p>
            <p className="text-[11px] text-blue-700 mt-1">
              Markdown-Hinweis: KI-Antworten nutzen Ueberschriften, Listen und Fettdruck.
            </p>
            {/* Zeitraum-Auswahl */}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="text-xs text-slate-500 font-medium">Ausgewerteter Zeitraum:</span>
              <div className="flex gap-1 p-0.5 bg-slate-100 rounded-lg">
                {CHAT_RANGES.map((r) => (
                  <button
                    key={r.value}
                    onClick={() => setSelectedRange(r.value)}
                    className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                      selectedRange === r.value
                        ? 'bg-white text-blue-600 shadow-sm'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => refetch()}
              className="inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold border border-slate-200 rounded-lg hover:bg-slate-50"
            >
              <RefreshCw className="w-4 h-4" /> Verlauf aktualisieren
            </button>
            <button
              onClick={() => clearMutation.mutate()}
              disabled={messages.length === 0 || clearMutation.isPending}
              className="inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold border border-red-200 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {clearMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />} Verlauf löschen
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => submitQuestion(prompt)}
              disabled={sendMutation.isPending}
              className="px-3 py-1.5 text-xs rounded-full bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100 disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>

        {candidateEntities.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Relevante Entitäten eingrenzen (optional)
            </p>
            <div className="flex flex-wrap gap-2">
              {candidateEntities.map((entity) => {
                const isSelected = selectedEntityIds.includes(entity.entity_id);
                return (
                  <button
                    key={entity.entity_id}
                    onClick={() => toggleEntity(entity.entity_id)}
                    className={`px-2.5 py-1 text-xs rounded-md border transition ${
                      isSelected
                        ? 'border-blue-400 bg-blue-600 text-white'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300'
                    }`}
                    title={entity.entity_id}
                  >
                    {entity.friendly_name || entity.entity_id}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Frage</label>
          <div className="flex gap-2">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="z.B. Warum steigt der Rücklauf in den letzten Stunden?"
              rows={3}
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  submitQuestion();
                }
              }}
            />
            <button
              onClick={() => submitQuestion()}
              disabled={sendMutation.isPending || !question.trim()}
              className="self-end inline-flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
            >
              {sendMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Senden
            </button>
          </div>
          <p className="text-[11px] text-slate-400">Mit Strg+Enter senden.</p>
        </div>

        {sendMutation.error && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-100 text-red-700 text-sm">
            Chat-Request fehlgeschlagen. Bitte erneut versuchen.
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <h4 className="font-semibold text-slate-900 mb-4">Verlauf für dieses Gerät</h4>

        {isHistoryLoading ? (
          <div className="py-10 text-center text-slate-500">Verlauf wird geladen…</div>
        ) : messages.length === 0 ? (
          <div className="py-10 text-center text-slate-500">Noch keine Chat-Nachrichten vorhanden.</div>
        ) : (
          <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
            {messages.map((message, index) => {
              const normalizedRole = (message.role || '').toLowerCase().trim();
              const isAssistant = normalizedRole === 'assistant' || normalizedRole === 'ai' || normalizedRole === 'bot' || normalizedRole === 'model';

              return (
                <div
                  key={`${message.created_at}-${index}`}
                  className={`p-3 rounded-xl border ${
                    isAssistant
                      ? 'bg-slate-50 border-slate-200 text-slate-800'
                      : 'bg-blue-600 border-blue-600 text-white'
                  }`}
                >
                  <div className="flex items-center justify-between gap-4 mb-1.5">
                    <span className="text-[11px] uppercase tracking-wide font-semibold opacity-80">
                      {isAssistant ? 'Assistent' : 'Techniker'}
                    </span>
                    <span className="text-[11px] opacity-70">
                      {new Date(message.created_at).toLocaleString('de-DE')}
                    </span>
                  </div>
                  {isAssistant ? (
                    <MarkdownMessage content={message.content} className="text-sm leading-6" />
                  ) : (
                    <p className="text-sm whitespace-pre-wrap leading-6">{message.content}</p>
                  )}
                </div>
              );
            })}
            {sendMutation.isPending && (
              <div className="p-3 rounded-xl border bg-slate-50 border-slate-200">
                <span className="text-[11px] uppercase tracking-wide font-semibold opacity-60 text-slate-600">Assistent</span>
                <div className="flex gap-1 mt-2 items-center h-5">
                  <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
                  <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
  );
};

export default DeviceChatPanel;
