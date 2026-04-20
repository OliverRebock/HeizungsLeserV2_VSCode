import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Mic, SendHorizontal, MessageSquareText, Loader2, AlertCircle, Activity, X, ChevronDown } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import api from '../lib/api';
import type { Device, HeatPumpChatResponse } from '../types/api';

type SpeechRecognitionAlternativeLike = {
  transcript: string;
};

type SpeechRecognitionResultLike = {
  0: SpeechRecognitionAlternativeLike;
  isFinal?: boolean;
  length: number;
};

type SpeechRecognitionEventLike = {
  results: ArrayLike<SpeechRecognitionResultLike>;
};

type SpeechRecognitionErrorEventLike = {
  error: string;
};

type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  meta?: string;
};

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

const getApiErrorMessage = (error: unknown, fallback: string) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;

    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    if (Array.isArray(detail)) {
      const combined = detail
        .map((item) => {
          if (typeof item === 'string') {
            return item;
          }
          if (typeof item === 'object' && item !== null && 'msg' in item && typeof item.msg === 'string') {
            return item.msg;
          }
          return '';
        })
        .filter((item): item is string => Boolean(item))
        .join(' ');
      if (combined) {
        return combined;
      }
    }

    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
};

const getRangeStartDate = (selectedRange: string) => {
  const fromDate = new Date();

  if (selectedRange === '24h') {
    fromDate.setHours(fromDate.getHours() - 24);
  } else if (selectedRange === '7d') {
    fromDate.setDate(fromDate.getDate() - 7);
  } else {
    fromDate.setDate(fromDate.getDate() - 30);
  }

  return fromDate;
};

const createChatMessage = (
  role: ChatMessage['role'],
  content: string,
  meta?: string,
): ChatMessage => ({
  id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  role,
  content,
  meta,
  createdAt: new Date().toISOString(),
});

const formatRecordingDuration = (seconds: number) => {
  const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
  const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
};

const getSpeechRecognitionErrorMessage = (error: string) => {
  switch (error) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Mikrofonzugriff wurde blockiert. Bitte Browserberechtigung freigeben.';
    case 'no-speech':
      return 'Keine Sprache erkannt. Bitte noch einmal sprechen.';
    case 'audio-capture':
      return 'Kein Mikrofon verfuegbar oder das Geraet liefert kein Audiosignal.';
    case 'network':
      return 'Die Spracherkennung konnte keine Verbindung herstellen.';
    default:
      return 'Die Spracheingabe konnte nicht gestartet werden.';
  }
};

const AnalysisChatWindowPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const chatScrollContainerRef = useRef<HTMLDivElement | null>(null);
  const chatBottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const autoScrollEnabledRef = useRef(true);
  const chatDraftRef = useRef('');

  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [recordingStartedAt, setRecordingStartedAt] = useState<number | null>(null);
  const [recordingDurationSeconds, setRecordingDurationSeconds] = useState(0);
  const [speechError, setSpeechError] = useState('');
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const selectedRange = (searchParams.get('range') === '24h' || searchParams.get('range') === '7d' || searchParams.get('range') === '30d')
    ? (searchParams.get('range') as '24h' | '7d' | '30d')
    : '24h';

  const parsedDeviceId = Number(searchParams.get('deviceId') ?? '0');
  const selectedDeviceId = Number.isFinite(parsedDeviceId) && parsedDeviceId > 0 ? parsedDeviceId : null;

  const speechRecognitionApi = typeof window !== 'undefined'
    ? window.SpeechRecognition ?? window.webkitSpeechRecognition
    : undefined;
  const speechSupported = Boolean(speechRecognitionApi);

  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const response = await api.get<Device[]>('/devices/');
      return response.data;
    },
  });

  const selectedDevice = useMemo(
    () => devices?.find((device) => device.id === selectedDeviceId) ?? null,
    [devices, selectedDeviceId],
  );

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  useEffect(() => {
    chatDraftRef.current = chatInput;
  }, [chatInput]);

  useEffect(() => {
    if (!isListening || recordingStartedAt === null) {
      setRecordingDurationSeconds(0);
      return;
    }

    const updateDuration = () => {
      const now = Date.now();
      setRecordingDurationSeconds(Math.max(0, Math.floor((now - recordingStartedAt) / 1000)));
    };

    updateDuration();
    const intervalId = window.setInterval(updateDuration, 250);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isListening, recordingStartedAt]);

  const scrollChatToBottom = (behavior: ScrollBehavior = 'smooth') => {
    const anchor = chatBottomAnchorRef.current;
    if (anchor) {
      anchor.scrollIntoView({ behavior, block: 'end' });
      return;
    }

    const container = chatScrollContainerRef.current;
    if (!container) {
      return;
    }
    container.scrollTo({ top: container.scrollHeight, behavior });
  };

  const handleChatScroll = () => {
    const container = chatScrollContainerRef.current;
    if (!container) {
      return;
    }

    const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    const nearBottom = distanceToBottom <= 80;

    autoScrollEnabledRef.current = nearBottom;
    setShowScrollToBottom(!nearBottom);
  };

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      if (!selectedDeviceId) {
        return null;
      }

      const fromDate = getRangeStartDate(selectedRange);
      const response = await api.post<HeatPumpChatResponse>(`/analysis/${selectedDeviceId}/chat`, {
        question: message,
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        language: 'de',
        history: chatMessages.map((item) => ({ role: item.role, content: item.content })),
      });

      return response.data;
    },
    onSuccess: (data) => {
      if (!data) {
        return;
      }

      const evidence = data.evidence?.slice(0, 3) ?? [];
      const appendix = evidence.length > 0
        ? `\n\nMessgrundlage:\n- ${evidence.join('\n- ')}`
        : '';

      const tf = data.timeframe;
      const periodLabel = tf.from_local && tf.to_local
        ? `${tf.from_local} – ${tf.to_local}`
        : `${tf.from} – ${tf.to}`;
      const metaLabel = `Intent: ${data.intent} | Zeitraum: ${periodLabel}`;

      setChatMessages((current) => [
        ...current,
        createChatMessage('assistant', `${data.answer}${appendix}`, metaLabel),
      ]);
      setSpeechError('');
    },
    onError: (error) => {
      setChatMessages((current) => [
        ...current,
        createChatMessage('assistant', getApiErrorMessage(error, 'Die Chat-Antwort konnte nicht erzeugt werden.'), 'Fehler'),
      ]);
    },
  });

  useEffect(() => {
    if (!autoScrollEnabledRef.current) {
      return;
    }

    scrollChatToBottom('smooth');
  }, [chatMessages, chatMutation.isPending]);

  const handleSendChatMessage = (messageOverride?: string) => {
    const trimmedMessage = (messageOverride ?? chatDraftRef.current).trim();
    if (!trimmedMessage || chatMutation.isPending) {
      return;
    }

    setSpeechError('');
    setChatMessages((current) => [
      ...current,
      createChatMessage('user', trimmedMessage, 'Frage vom Monteur'),
    ]);
    autoScrollEnabledRef.current = true;
    setShowScrollToBottom(false);
    requestAnimationFrame(() => scrollChatToBottom('smooth'));
    setChatInput('');
    chatDraftRef.current = '';
    chatMutation.mutate(trimmedMessage);
  };

  const startSpeechInput = () => {
    if (!speechRecognitionApi) {
      setSpeechError('Dieser Browser unterstuetzt keine Spracheingabe. Empfohlen: aktuelles Chrome oder Edge.');
      return;
    }

    if (isListening) {
      return;
    }

    setSpeechError('');

    const recognition = new speechRecognitionApi();
    recognition.lang = 'de-DE';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? '')
        .join(' ')
        .trim();

      setChatInput(transcript);
      chatDraftRef.current = transcript;
    };

    recognition.onerror = (event) => {
      setSpeechError(getSpeechRecognitionErrorMessage(event.error));
      setIsListening(false);
      setRecordingStartedAt(null);
    };

    recognition.onend = () => {
      setIsListening(false);
      setRecordingStartedAt(null);
    };

    recognitionRef.current = recognition;
    setIsListening(true);
    setRecordingStartedAt(Date.now());
    recognition.start();
  };

  const stopSpeechInput = () => {
    if (!isListening) {
      return;
    }

    recognitionRef.current?.stop();
  };

  const toggleSpeechInput = () => {
    if (isListening) {
      stopSpeechInput();
      return;
    }

    startSpeechInput();
  };

  if (!selectedDeviceId) {
    return (
      <div className="min-h-screen bg-slate-100 p-6 md:p-10">
        <div className="mx-auto max-w-2xl rounded-2xl border border-red-200 bg-white p-8 text-center">
          <AlertCircle className="mx-auto mb-4 h-8 w-8 text-red-500" />
          <h1 className="text-lg font-bold text-slate-900">Einsatz-Chat konnte nicht gestartet werden</h1>
          <p className="mt-2 text-sm text-slate-600">Es wurde kein gueltiges Geraet uebergeben. Bitte den Chat erneut aus dem Schnellcheck starten.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_12%_12%,#dbeafe_0%,transparent_38%),radial-gradient(circle_at_88%_82%,#fde68a_0%,transparent_35%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_42%,#f8fafc_100%)] px-3 pb-[calc(env(safe-area-inset-bottom)+14px)] pt-4 md:p-8">
      <button
        type="button"
        onClick={() => window.close()}
        className="fixed right-14 top-[calc(env(safe-area-inset-top)+10px)] z-50 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200/90 bg-white/95 text-slate-600 shadow-[0_6px_20px_rgba(15,23,42,0.16)] backdrop-blur transition hover:bg-slate-50 sm:right-4 md:right-6 md:top-6"
        title="Fenster schliessen"
        aria-label="Fenster schliessen"
      >
        <X className="h-4 w-4" />
      </button>
      <div className="mx-auto max-w-5xl space-y-3 md:space-y-4">
        <div className="rounded-[22px] border border-slate-200/80 bg-white/90 p-4 shadow-[0_10px_30px_rgba(15,23,42,0.08)] backdrop-blur md:p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-gradient-to-br from-slate-900 to-blue-700 p-2.5 text-white shadow-sm">
                <MessageSquareText className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight text-slate-900">Einsatz-Chat</h1>
                <p className="text-sm text-slate-600">Folgefragen per Text oder Mikrofon. Antwort kommt in kurzer Monteur-Sprache.</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-[11px] font-semibold text-blue-700">
                Live-Transkript + KI-Antwort
              </div>
            </div>
          </div>

          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100/80 px-2.5 py-1 text-slate-700">
                <Activity className="h-3.5 w-3.5" />
                {selectedDevice?.display_name ?? `Geraet ${selectedDeviceId}`}
              </span>
              <span className="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 font-semibold uppercase tracking-wide text-indigo-700">
                Zeitraum: {selectedRange}
              </span>
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-[24px] border border-slate-200/80 bg-white/95 shadow-[0_14px_40px_rgba(30,41,59,0.1)] backdrop-blur">
          <div className="space-y-3 p-4 md:space-y-4 md:p-6">
            <div
              ref={chatScrollContainerRef}
              onScroll={handleChatScroll}
              className="max-h-[50vh] space-y-3 overflow-y-auto pr-1 md:max-h-[56vh]"
            >
              {chatMessages.length === 0 && !chatMutation.isPending && (
                <div className="flex justify-start">
                  <div className="max-w-[92%] rounded-2xl border border-cyan-100 bg-gradient-to-br from-cyan-50 to-slate-50 px-4 py-3 text-slate-800 shadow-sm">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-700">Bereit</p>
                    <p className="text-sm leading-relaxed text-slate-700">
                      Einfach losschießen: zum Beispiel mit Fragen wie „Taktet die Wärmepumpe auffällig oft?“, „Wie hoch ist der Durchfluss von PC0 und PC1?“ oder „Läuft die Anlage gerade fehlerfrei?“ — kurz gesagt: Frag, was immer du über die Anlage wissen willst.
                    </p>
                  </div>
                </div>
              )}

              {chatMessages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[92%] rounded-2xl border px-4 py-3 shadow-sm ${
                      message.role === 'user'
                        ? 'border-blue-500 bg-gradient-to-br from-blue-600 to-indigo-600 text-white'
                        : 'border-slate-200 bg-white text-slate-800'
                    }`}
                  >
                    {message.meta && (
                      <p
                        className={`mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] ${
                          message.role === 'user' ? 'text-blue-100' : 'text-slate-500'
                        }`}
                      >
                        {message.meta}
                      </p>
                    )}
                    <p className="whitespace-pre-line text-sm leading-relaxed">{message.content}</p>
                    <p className={`mt-2 text-[10px] ${message.role === 'user' ? 'text-blue-100/80' : 'text-slate-400'}`}>
                      {new Date(message.createdAt).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))}

              {chatMutation.isPending && (
                <div className="flex justify-start">
                  <div className="max-w-[90%] rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-800 shadow-sm">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Assistent denkt</p>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Die naechste Monteur-Antwort wird erzeugt...
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatBottomAnchorRef} aria-hidden="true" />
            </div>

            {showScrollToBottom && (
              <div className="flex justify-center">
                <button
                  type="button"
                  onClick={() => {
                    autoScrollEnabledRef.current = true;
                    setShowScrollToBottom(false);
                    scrollChatToBottom('smooth');
                  }}
                  className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white/95 px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
                >
                  <ChevronDown className="h-3.5 w-3.5" />
                  Neueste Nachricht
                </button>
              </div>
            )}

            <div className="sticky bottom-0 -mx-4 border-t border-slate-200 bg-white/95 p-3 backdrop-blur md:-mx-6 md:p-4">
              <div className="rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white p-3 shadow-sm">
              <textarea
                rows={3}
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    handleSendChatMessage();
                  }
                }}
                placeholder="Frage zur Waermepumpe, z. B. 'Laeuft die Anlage aktuell normal?'"
                className="w-full rounded-xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-700 shadow-[inset_0_1px_2px_rgba(15,23,42,0.06)] outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />

              <p className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] text-blue-700">
                Es werden nur relevante Influx-Daten zur Frage geladen, keine Vollabfrage beim Start.
              </p>

              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="text-[11px] text-slate-500">
                  Mit Enter senden, mit Shift + Enter Zeilenumbruch. Mikrofon antippen zum Starten, erneut tippen zum Stoppen.
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={toggleSpeechInput}
                    disabled={!speechSupported && !isListening}
                    title={isListening ? 'Aufnahme stoppen' : 'Aufnahme starten'}
                    aria-label={isListening ? 'Aufnahme stoppen' : 'Aufnahme starten'}
                    className={`inline-flex h-11 w-11 items-center justify-center rounded-full border shadow-sm transition ${
                      isListening
                        ? 'border-red-200 bg-red-50 text-red-700 shadow-inner'
                        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50'
                    }`}
                  >
                    <Mic className="h-4 w-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => handleSendChatMessage()}
                    disabled={!chatInput.trim() || chatMutation.isPending}
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-[0_8px_20px_rgba(37,99,235,0.28)] transition hover:from-blue-700 hover:to-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <SendHorizontal className="h-3.5 w-3.5" />
                    Senden
                  </button>
                </div>
              </div>

              {isListening && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-red-700">
                    <div className="flex items-center gap-2 font-semibold">
                      <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" />
                      Aufnahme laeuft...
                    </div>
                    <span className="font-mono text-xs">{formatRecordingDuration(recordingDurationSeconds)}</span>
                  </div>
                  <div className="mt-2 flex items-end gap-1">
                    <span className="h-2 w-1 animate-pulse rounded bg-red-300" />
                    <span className="h-4 w-1 animate-pulse rounded bg-red-400 [animation-delay:120ms]" />
                    <span className="h-3 w-1 animate-pulse rounded bg-red-300 [animation-delay:240ms]" />
                    <span className="h-5 w-1 animate-pulse rounded bg-red-500 [animation-delay:360ms]" />
                    <span className="h-3 w-1 animate-pulse rounded bg-red-300 [animation-delay:480ms]" />
                    <span className="h-4 w-1 animate-pulse rounded bg-red-400 [animation-delay:600ms]" />
                    <span className="h-2 w-1 animate-pulse rounded bg-red-300 [animation-delay:720ms]" />
                  </div>
                </div>
              )}

              {!speechSupported && (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
                  Spracheingabe ist nur in Browsern mit Web-Speech-Unterstuetzung verfuegbar, typischerweise Chrome oder Edge.
                </p>
              )}

                {speechError && (
                  <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-700">
                    {speechError}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalysisChatWindowPage;
