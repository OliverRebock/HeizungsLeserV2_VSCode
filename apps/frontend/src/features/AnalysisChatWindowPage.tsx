import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Mic, Square, SendHorizontal, MessageSquareText, Loader2, AlertCircle, Activity, X } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import api from '../lib/api';
import type { AnalysisResponse, Device } from '../types/api';

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

const ISSUE_OPTIONS = [
  { value: 'quick-check', focus: 'Schneller Vor-Ort-Check mit Fokus auf die wichtigste Spur und die naechsten Pruefschritte.' },
  { value: 'error-code', focus: 'Aktuelle Stoerung oder Fehlercode schnell einordnen und die wahrscheinlichste Ursache priorisieren.' },
  { value: 'no-heat', focus: 'Pruefen, warum die Anlage aktuell keine oder zu wenig Heizleistung liefert.' },
  { value: 'cycling', focus: 'Auffaellige Taktung bewerten und die wahrscheinlichste technische Ursache benennen.' },
  { value: 'hot-water', focus: 'Warmwasserproblem schnell einordnen und die wichtigsten Pruefpunkte nennen.' },
  { value: 'temperatures', focus: 'Unplausible Temperaturen, Fuehlerwerte oder Spreizungen gezielt bewerten.' },
] as const;

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

const buildChatAnalysisFocus = (
  selectedIssue: string,
  problemNote: string,
  chatMessages: ChatMessage[],
  latestMessage: string,
  baseAnalysis?: AnalysisResponse | null,
) => {
  const selectedOption = ISSUE_OPTIONS.find((option) => option.value === selectedIssue) ?? ISSUE_OPTIONS[0];
  const recentMessages = chatMessages
    .slice(-6)
    .map((message) => `${message.role === 'user' ? 'Monteur' : 'Assistent'}: ${message.content}`)
    .join(' | ');

  return [
    `Chat-Modus fuer Heizungsbauer zum Einsatzfall: ${selectedOption.value}.`,
    'Antworte wie ein technischer Assistent im Vor-Ort-Einsatz.',
    'Nutze alle verfuegbaren Messdaten im gewaehlten Zeitraum fuer die Antwort.',
    'Erst kurz den Zustand einordnen, dann maximal 3 konkrete Schritte nennen.',
    'Verwende klare Monteur-Sprache, keine Management-Formulierungen.',
    problemNote.trim() ? `Vor-Ort-Notiz: ${problemNote.trim()}.` : null,
    baseAnalysis?.summary ? `Bisherige Haupteinschaetzung: ${baseAnalysis.summary}.` : null,
    recentMessages ? `Bisheriger Chatverlauf: ${recentMessages}.` : null,
    `Neue Frage vom Monteur: ${latestMessage.trim()}.`,
  ]
    .filter(Boolean)
    .join(' ');
};

const buildAssistantChatMessage = (analysis: AnalysisResponse) => {
  const parts: string[] = [analysis.summary];

  if (analysis.detected_error_codes.length > 0) {
    const firstCode = analysis.detected_error_codes[0];
    parts.push(`Fehlercode im Fokus: ${firstCode.code} ${firstCode.label}.`);
  }

  if (analysis.findings[0]) {
    parts.push(`Wichtigster Befund: ${analysis.findings[0].title}. ${analysis.findings[0].description}`);
  }

  if (analysis.recommended_followup_checks.length > 0) {
    const steps = analysis.recommended_followup_checks.slice(0, 3);
    parts.push(`Naechste Schritte: ${steps.map((step, index) => `${index + 1}. ${step}`).join(' ')}`);
  } else if (analysis.optimization_hints.length > 0) {
    const steps = analysis.optimization_hints.slice(0, 2);
    parts.push(`Pruefhinweise: ${steps.join(' ')}`);
  }

  return parts.join('\n\n');
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
  const initialRequestStartedRef = useRef(false);
  const chatDraftRef = useRef('');
  const shouldAutoSendChatRef = useRef(false);

  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [baseAnalysis, setBaseAnalysis] = useState<AnalysisResponse | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<string | null>(null);
  const [chatStarted, setChatStarted] = useState(false);
  const [heatingDataLoaded, setHeatingDataLoaded] = useState(false);
  const [isLoadingHeatingData, setIsLoadingHeatingData] = useState(false);
  const selectedRange = (searchParams.get('range') === '24h' || searchParams.get('range') === '7d' || searchParams.get('range') === '30d')
    ? (searchParams.get('range') as '24h' | '7d' | '30d')
    : '24h';

  const parsedDeviceId = Number(searchParams.get('deviceId') ?? '0');
  const selectedDeviceId = Number.isFinite(parsedDeviceId) && parsedDeviceId > 0 ? parsedDeviceId : null;
  const problemNote = searchParams.get('note') ?? '';

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
    if (!selectedDeviceId || initialRequestStartedRef.current) {
      return;
    }

    initialRequestStartedRef.current = true;
    setHeatingDataLoaded(false);
    setIsLoadingHeatingData(true);
    setChatMessages([]);
    setSelectedIssue(null);
    setChatStarted(false);

    const loadData = async () => {
      const fromDate = getRangeStartDate(selectedRange);

      try {
        const response = await api.post<AnalysisResponse>(`/analysis/${selectedDeviceId}`, {
          from: fromDate.toISOString(),
          to: new Date().toISOString(),
          analysis_focus: 'Daten laden ohne Analyse.',
          language: 'de',
        });

        setBaseAnalysis(response.data);
        setHeatingDataLoaded(true);
      } catch (error) {
        setChatMessages([
          createChatMessage('assistant', getApiErrorMessage(error, 'Heizungsdaten konnten nicht geladen werden.'), 'Fehler'),
        ]);
      } finally {
        setIsLoadingHeatingData(false);
      }
    };

    loadData();
  }, [selectedDeviceId, selectedRange]);

  const startChatWithIssueMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDeviceId || !selectedIssue || !baseAnalysis) {
        return null;
      }

      const fromDate = getRangeStartDate(selectedRange);
      const selectedOption = ISSUE_OPTIONS.find((option) => option.value === selectedIssue) ?? ISSUE_OPTIONS[0];
      
      const focus = [
        selectedOption.focus,
        'Die Antwort ist für einen Heizungsbauer direkt beim Kunden gedacht.',
        'Antworte kurz, direkt und praxisnah.',
        'Nenne zuerst die wahrscheinlichste Ursache und danach maximal 3 konkrete Prüfschritte vor Ort.',
        'Vermeide lange Erklärtexte und zu viele Detailanalysen.',
        problemNote.trim() ? `Hinweis vom Einsatz vor Ort: ${problemNote.trim()}` : null,
      ]
        .filter(Boolean)
        .join(' ');

      const response = await api.post<AnalysisResponse>(`/analysis/${selectedDeviceId}`, {
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        analysis_focus: focus,
        language: 'de',
      });

      return response.data;
    },
    onSuccess: (data) => {
      if (!data) {
        return;
      }

      setBaseAnalysis(data);
      setChatStarted(true);
      setChatMessages([
        createChatMessage(
          'assistant',
          buildAssistantChatMessage(data),
          'Erstantwort zum ausgewählten Problem',
        ),
      ]);
    },
    onError: (error) => {
      setChatMessages([
        createChatMessage('assistant', getApiErrorMessage(error, 'Der Schnellcheck konnte nicht geladen werden.'), 'Fehler'),
      ]);
    },
  });

  const handleSelectIssue = (issue: string) => {
    setSelectedIssue(issue);
    startChatWithIssueMutation.mutate();
  }

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      if (!selectedDeviceId) {
        return null;
      }

      const fromDate = getRangeStartDate(selectedRange);
      const response = await api.post<AnalysisResponse>(`/analysis/${selectedDeviceId}`, {
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        analysis_focus: buildChatAnalysisFocus(selectedIssue ?? 'quick-check', problemNote, chatMessages, message, baseAnalysis),
        language: 'de',
      });

      return response.data;
    },
    onSuccess: (data) => {
      if (!data) {
        return;
      }

      setBaseAnalysis(data);
      setChatStarted(true);
      setChatMessages((current) => [
        ...current,
        createChatMessage('assistant', buildAssistantChatMessage(data), 'Antwort aus dem Einsatz-Chat'),
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
    setChatInput('');
    chatDraftRef.current = '';
    chatMutation.mutate(trimmedMessage);
  };

  const startSpeechInput = (autoSendOnEnd = false) => {
    if (!speechRecognitionApi) {
      setSpeechError('Dieser Browser unterstuetzt keine Spracheingabe. Empfohlen: aktuelles Chrome oder Edge.');
      return;
    }

    if (isListening) {
      return;
    }

    shouldAutoSendChatRef.current = autoSendOnEnd;
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
      shouldAutoSendChatRef.current = false;
    };

    recognition.onend = () => {
      setIsListening(false);
      const shouldAutoSend = shouldAutoSendChatRef.current;
      shouldAutoSendChatRef.current = false;

      if (shouldAutoSend) {
        handleSendChatMessage(chatDraftRef.current);
      }
    };

    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  };

  const stopSpeechInput = () => {
    if (!isListening) {
      return;
    }

    recognitionRef.current?.stop();
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
    <div className="min-h-screen bg-gradient-to-b from-slate-100 via-slate-50 to-white p-4 md:p-8">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-slate-900 p-2.5 text-white">
                <MessageSquareText className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900">Einsatz-Chat</h1>
                <p className="text-sm text-slate-500">Folgefragen per Text oder Mikrofon stellen, Antwort kommt in kurzer Monteur-Sprache.</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-semibold text-slate-600">
                Live-Transkript + KI-Antwort
              </div>
              <button
                type="button"
                onClick={() => window.close()}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-500 hover:bg-slate-50"
                title="Fenster schliessen"
                aria-label="Fenster schliessen"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1">
                <Activity className="h-3.5 w-3.5" />
                {selectedDevice?.display_name ?? `Geraet ${selectedDeviceId}`}
              </span>
              <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 uppercase">
                Zeitraum: {selectedRange}
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="p-5 md:p-6 space-y-4">
            <div className="max-h-[56vh] overflow-y-auto space-y-3 pr-1">
              {isLoadingHeatingData && !heatingDataLoaded && (
                <div className="flex justify-start">
                  <div className="max-w-[90%] rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-800 shadow-sm">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Daten werden geladen</p>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Heizungsdaten werden geladen...
                    </div>
                  </div>
                </div>
              )}

              {startChatWithIssueMutation.isPending && chatMessages.length === 0 && (
                <div className="flex justify-start">
                  <div className="max-w-[90%] rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-800 shadow-sm">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Analyse laeuft</p>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Erstantwort wird erstellt...
                    </div>
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
                        ? 'border-blue-600 bg-blue-600 text-white'
                        : 'border-slate-200 bg-slate-50 text-slate-800'
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
                  <div className="max-w-[90%] rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-800 shadow-sm">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Assistent denkt</p>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Die naechste Monteur-Antwort wird erzeugt...
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 space-y-3">
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
                placeholder="Frage an die KI, z. B. 'Ist der Fehler eher hydraulisch oder elektrisch?'"
                className="w-full rounded-xl border border-white bg-white px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />

              {!chatStarted && heatingDataLoaded && (
                <p className="text-[11px] text-blue-700 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
                  Das Chatfenster ist bereit. Du kannst sofort per Text oder Sprache starten. Die Problemwahl unten ist optional und schärft nur den Fokus.
                </p>
              )}

              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="text-[11px] text-slate-500">
                  Mit Enter senden, mit Shift + Enter Zeilenumbruch. Mikrofon gedrueckt halten, sprechen, loslassen: dann wird automatisch gesendet.
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onPointerDown={(event) => {
                      event.preventDefault();
                      startSpeechInput(true);
                    }}
                    onPointerUp={(event) => {
                      event.preventDefault();
                      stopSpeechInput();
                    }}
                    onPointerLeave={() => {
                      stopSpeechInput();
                    }}
                    onPointerCancel={() => {
                      stopSpeechInput();
                    }}
                    disabled={!speechSupported && !isListening}
                    title={isListening ? 'Spracheingabe laeuft' : 'Zum Sprechen gedrueckt halten'}
                    aria-label={isListening ? 'Spracheingabe laeuft' : 'Zum Sprechen gedrueckt halten'}
                    className={`inline-flex h-11 w-11 select-none touch-none items-center justify-center rounded-full border transition ${
                      isListening
                        ? 'scale-95 border-red-200 bg-red-50 text-red-700 shadow-inner'
                        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50'
                    }`}
                  >
                    {isListening ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  </button>

                  <button
                    type="button"
                    onClick={() => handleSendChatMessage()}
                    disabled={!chatInput.trim() || chatMutation.isPending}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <SendHorizontal className="h-3.5 w-3.5" />
                    Senden
                  </button>
                </div>
              </div>

              {!speechSupported && (
                <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  Spracheingabe ist nur in Browsern mit Web-Speech-Unterstuetzung verfuegbar, typischerweise Chrome oder Edge.
                </p>
              )}

                {speechError && (
                  <p className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                    {speechError}
                  </p>
                )}
              </div>

              {!chatStarted && heatingDataLoaded && (
                <div className="space-y-4">
                  <div className="rounded-xl bg-blue-50 border border-blue-200 p-4">
                    <p className="text-sm font-semibold text-blue-900 mb-4">Welches Problem möchtest du analysieren?</p>
                    <div className="grid grid-cols-1 gap-2">
                      {ISSUE_OPTIONS.map((issue) => (
                        <button
                          key={issue.value}
                          onClick={() => handleSelectIssue(issue.value)}
                          disabled={startChatWithIssueMutation.isPending}
                          className="w-full rounded-lg border border-blue-300 bg-white px-4 py-3 text-left text-sm font-medium text-blue-900 hover:bg-blue-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {issue.value === 'quick-check' && 'Allgemeiner Schnellcheck'}
                          {issue.value === 'error-code' && 'Fehlercode / Störung'}
                          {issue.value === 'no-heat' && 'Keine Heizleistung'}
                          {issue.value === 'cycling' && 'Viele Starts / Taktung'}
                          {issue.value === 'hot-water' && 'Warmwasserproblem'}
                          {issue.value === 'temperatures' && 'Temperaturproblem'}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalysisChatWindowPage;
