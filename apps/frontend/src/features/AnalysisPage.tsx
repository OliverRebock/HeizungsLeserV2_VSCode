import React, { useEffect, useRef, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import axios from 'axios';
import { 
  Brain, 
  ChevronRight, 
  AlertTriangle, 
  CheckCircle2, 
  Info, 
  Activity, 
  Calendar,
  Loader2,
  AlertCircle,
  Lightbulb,
  Stethoscope,
  ArrowRight,
  ShieldCheck,
  Flag,
  Mic,
  Square,
  Wrench,
  Thermometer,
  Siren,
  Clock3,
  SendHorizontal,
  MessageSquareText
} from 'lucide-react';
import api from '../lib/api';
import { useAuthStore } from '../hooks/useAuth';
import type { Device, AnalysisResponse, DeepAnalysisResponse, DetectedErrorCode } from '../types/api';

const TIME_RANGES = [
  { label: 'Letzte 24h', value: '24h' },
  { label: 'Letzte 7 Tage', value: '7d' },
  { label: 'Letzte 30 Tage', value: '30d' },
];

const ISSUE_OPTIONS = [
  {
    label: 'Allgemeiner Schnellcheck',
    value: 'quick-check',
    focus: 'Schneller Vor-Ort-Check mit Fokus auf die wichtigste Spur und die nächsten Prüfschritte.',
  },
  {
    label: 'Fehlercode / Störung',
    value: 'error-code',
    focus: 'Aktuelle Störung oder Fehlercode schnell einordnen und die wahrscheinlichste Ursache priorisieren.',
  },
  {
    label: 'Keine Heizleistung',
    value: 'no-heat',
    focus: 'Prüfen, warum die Anlage aktuell keine oder zu wenig Heizleistung liefert.',
  },
  {
    label: 'Viele Starts / Taktung',
    value: 'cycling',
    focus: 'Auffällige Taktung bewerten und die wahrscheinlichste technische Ursache benennen.',
  },
  {
    label: 'Warmwasserproblem',
    value: 'hot-water',
    focus: 'Warmwasserproblem schnell einordnen und die wichtigsten Prüfpunkte nennen.',
  },
  {
    label: 'Temperaturproblem',
    value: 'temperatures',
    focus: 'Unplausible Temperaturen, Fühlerwerte oder Spreizungen gezielt bewerten.',
  },
];

const SEVERITY_PRIORITY: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

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

type SpeechTarget = 'note' | 'chat';

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

const buildAnalysisFocus = (selectedIssue: string, problemNote: string) => {
  const selectedOption = ISSUE_OPTIONS.find((option) => option.value === selectedIssue) ?? ISSUE_OPTIONS[0];
  const note = problemNote.trim();

  return [
    selectedOption.focus,
    'Die Antwort ist für einen Heizungsbauer direkt beim Kunden gedacht.',
    'Antworte kurz, direkt und praxisnah.',
    'Nenne zuerst die wahrscheinlichste Ursache und danach maximal 3 konkrete Prüfschritte vor Ort.',
    'Vermeide lange Erklärtexte und zu viele Detailanalysen.',
    note ? `Hinweis vom Einsatz vor Ort: ${note}` : null,
  ]
    .filter(Boolean)
    .join(' ');
};

const buildDeepAnalysisFocus = (selectedIssue: string, problemNote: string) => {
  const selectedOption = ISSUE_OPTIONS.find((option) => option.value === selectedIssue) ?? ISSUE_OPTIONS[0];
  const note = problemNote.trim();

  return [
    `Vertiefte technische Analyse für folgenden Einsatzfall: ${selectedOption.label}.`,
    'Antworte weiterhin kompakt und nenne nur die wichtigsten Ursachen und Diagnoseschritte.',
    'Maximal 3 Ursachen und maximal 5 konkrete Prüfschritte.',
    note ? `Zusätzlicher Einsatzhinweis: ${note}` : null,
  ]
    .filter(Boolean)
    .join(' ');
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
    `Chat-Modus für Heizungsbauer zum Einsatzfall: ${selectedOption.label}.`,
    'Antworte wie ein technischer Assistent im Vor-Ort-Einsatz.',
    'Erst kurz den Zustand einordnen, dann maximal 3 konkrete Schritte nennen.',
    'Verwende klare Monteur-Sprache, keine Management-Formulierungen.',
    problemNote.trim() ? `Vor-Ort-Notiz: ${problemNote.trim()}.` : null,
    baseAnalysis?.summary ? `Bisherige Haupteinschätzung: ${baseAnalysis.summary}.` : null,
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
    parts.push(`Nächste Schritte: ${steps.map((step, index) => `${index + 1}. ${step}`).join(' ')}`);
  } else if (analysis.optimization_hints.length > 0) {
    const steps = analysis.optimization_hints.slice(0, 2);
    parts.push(`Prüfhinweise: ${steps.join(' ')}`);
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

const getRangeStartDate = (selectedRange: string, forDeepAnalysis = false) => {
  const fromDate = new Date();

  if (forDeepAnalysis) {
    if (selectedRange === '30d') {
      fromDate.setDate(fromDate.getDate() - 30);
      return fromDate;
    }

    fromDate.setDate(fromDate.getDate() - 7);
    return fromDate;
  }

  if (selectedRange === '24h') fromDate.setHours(fromDate.getHours() - 24);
  else if (selectedRange === '7d') fromDate.setDate(fromDate.getDate() - 7);
  else if (selectedRange === '30d') fromDate.setDate(fromDate.getDate() - 30);

  return fromDate;
};

const getPrimarySignal = (
  analysisResult: AnalysisResponse,
  deepAnalysisResult: DeepAnalysisResponse | null,
) => {
  if (deepAnalysisResult?.suspected_causes?.length) {
    return {
      title: 'Wahrscheinlichste Ursache',
      description: deepAnalysisResult.suspected_causes[0],
    };
  }

  if (analysisResult.detected_error_codes?.length) {
    const errorCode = analysisResult.detected_error_codes[0];
    const seenWindow = formatDetectedErrorSeenWindow(errorCode);
    return {
      title: `Fehlercode ${errorCode.code}`,
      description: seenWindow
        ? `${errorCode.label} (${errorCode.source_label}). ${seenWindow}.`
        : `${errorCode.label} (${errorCode.source_label})`,
    };
  }

  const topFinding = [...analysisResult.findings].sort(
    (left, right) => (SEVERITY_PRIORITY[right.severity] ?? 0) - (SEVERITY_PRIORITY[left.severity] ?? 0),
  )[0];

  if (topFinding) {
    return {
      title: topFinding.title,
      description: topFinding.description,
    };
  }

  if (analysisResult.anomalies.length > 0) {
    return {
      title: analysisResult.anomalies[0].title,
      description: analysisResult.anomalies[0].description,
    };
  }

  return {
    title: 'Keine dominante Spur erkannt',
    description: 'Die Auswertung sieht keine einzelne Hauptursache. Prüfen Sie die nächsten Schritte vor Ort.',
  };
};

const getQuickChecks = (
  analysisResult: AnalysisResponse,
  deepAnalysisResult: DeepAnalysisResponse | null,
) => {
  if (deepAnalysisResult?.diagnostic_steps?.length) {
    return deepAnalysisResult.diagnostic_steps.slice(0, 5);
  }
  if (analysisResult.recommended_followup_checks?.length) {
    return analysisResult.recommended_followup_checks.slice(0, 3);
  }
  return analysisResult.optimization_hints.slice(0, 3);
};

const formatAnalysisTimestamp = (timestamp?: string | null) => {
  if (!timestamp) {
    return null;
  }

  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return date.toLocaleString('de-DE');
};

const formatDetectedErrorSeenWindow = (errorCode: DetectedErrorCode) => {
  const firstSeenAt = formatAnalysisTimestamp(errorCode.first_seen_at);
  const lastSeenAt = formatAnalysisTimestamp(errorCode.last_seen_at);
  const seenCount = errorCode.seen_count ?? 1;

  if (!firstSeenAt && !lastSeenAt) {
    return null;
  }

  let text = '';
  if (firstSeenAt && lastSeenAt && firstSeenAt !== lastSeenAt) {
    text = `Im Zeitraum gesehen von ${firstSeenAt} bis ${lastSeenAt}`;
  } else {
    text = `Im Zeitraum gesehen: ${firstSeenAt ?? lastSeenAt}`;
  }

  if (seenCount > 1) {
    return `${text} (${seenCount} Messpunkte)`;
  }

  return text;
};

const getAnalysisSearchText = (
  analysisResult: AnalysisResponse,
  deepAnalysisResult: DeepAnalysisResponse | null,
) => {
  return [
    analysisResult.summary,
    ...analysisResult.findings.map((item) => `${item.title} ${item.description} ${item.evidence.join(' ')}`),
    ...analysisResult.anomalies.map((item) => `${item.title} ${item.description}`),
    ...analysisResult.optimization_hints,
    ...analysisResult.recommended_followup_checks,
    ...analysisResult.detected_error_codes.map((item) => `${item.code} ${item.label} ${item.observed_value}`),
    ...(analysisResult.error_candidates ?? []).map((item) => `${item.label} ${item.raw_value} ${item.classification}`),
    ...(deepAnalysisResult?.suspected_causes ?? []),
    ...(deepAnalysisResult?.diagnostic_steps ?? []),
  ]
    .join(' ')
    .toLowerCase();
};

const hasAnyTerm = (text: string, terms: string[]) => {
  return terms.some((term) => text.includes(term));
};

const getPriorityLabel = (analysisResult: AnalysisResponse) => {
  const normalizedStatus = analysisResult.overall_status.toLowerCase();
  if (
    normalizedStatus.includes('kritisch') ||
    analysisResult.findings.some((item) => item.severity === 'critical') ||
    (analysisResult.error_candidates ?? []).some((item) => item.classification === 'active')
  ) {
    return 'Sofort prüfen';
  }

  if (
    normalizedStatus.includes('auffällig') ||
    analysisResult.findings.some((item) => item.severity === 'high') ||
    analysisResult.detected_error_codes.length > 0
  ) {
    return 'Heute prüfen';
  }

  return 'Beobachten';
};

const getWorkbenchFocus = (selectedIssue: string) => {
  switch (selectedIssue) {
    case 'error-code':
      return 'Regler / Fehlerspeicher / Störhistorie';
    case 'no-heat':
      return 'Hydraulik / Freigaben / Verdichter';
    case 'cycling':
      return 'Regelung / Volumenstrom / Taktung';
    case 'hot-water':
      return 'Warmwasserbereitung / Umschaltung / Speicher';
    case 'temperatures':
      return 'Sensorik / Fühler / Temperaturwerte';
    default:
      return 'Gesamtsystem / Störungslage / Zeitbezug';
  }
};

type SnapshotTone = 'critical' | 'attention' | 'stable' | 'neutral';

type SnapshotItem = {
  label: string;
  value: string;
  detail: string;
  tone: SnapshotTone;
  icon: 'function' | 'heat' | 'urgency' | 'workbench';
};

const getSnapshotToneClasses = (tone: SnapshotTone) => {
  switch (tone) {
    case 'critical':
      return 'border-red-400/20 bg-red-500/10';
    case 'attention':
      return 'border-amber-300/20 bg-amber-400/10';
    case 'stable':
      return 'border-sky-300/20 bg-sky-400/10';
    default:
      return 'border-white/10 bg-white/5';
  }
};

const getQuickSnapshotItems = (
  analysisResult: AnalysisResponse,
  deepAnalysisResult: DeepAnalysisResponse | null,
  selectedIssue: string,
  quickChecks: string[],
): SnapshotItem[] => {
  const normalizedStatus = analysisResult.overall_status.toLowerCase();
  const searchText = getAnalysisSearchText(analysisResult, deepAnalysisResult);
  const hasCriticalFinding = analysisResult.findings.some((item) => item.severity === 'critical');
  const hasHighFinding = analysisResult.findings.some((item) => item.severity === 'high');
  const hasDetectedErrorCode = analysisResult.detected_error_codes.length > 0;
  const hasActiveError = (analysisResult.error_candidates ?? []).some((item) => item.classification === 'active');
  const hasHistoricalError = (analysisResult.error_candidates ?? []).some((item) => item.classification === 'historical');
  const hasHeatTopic = selectedIssue === 'no-heat' || selectedIssue === 'hot-water' || hasAnyTerm(searchText, ['heizleistung', 'warmwasser', 'keine wärme', 'kein warmwasser']);
  const hasSensorTopic = selectedIssue === 'temperatures' || hasAnyTerm(searchText, ['sensor', 'fühler', 'temperatur', 'plaus', 'spreizung']);
  const hasHydraulicTopic = hasAnyTerm(searchText, ['hydraul', 'volumenstrom', 'vorlauf', 'rücklauf', 'pumpe']);
  const hasCyclingTopic = selectedIssue === 'cycling' || hasAnyTerm(searchText, ['takt', 'takten', 'taktung', 'umschaltung', 'zustandswechsel', 'unruhig']);
  const primarySeenWindow = analysisResult.detected_error_codes[0]
    ? formatDetectedErrorSeenWindow(analysisResult.detected_error_codes[0])
    : null;

  const functionItem: SnapshotItem = {
    label: 'Funktion',
    value: hasActiveError || hasCriticalFinding || normalizedStatus.includes('kritisch')
      ? 'Störung aktiv'
      : hasDetectedErrorCode || hasHighFinding || normalizedStatus.includes('auffällig') || hasHistoricalError
        ? 'Läuft mit Auffälligkeiten'
        : 'Läuft ohne akute Störung',
    detail: hasActiveError
      ? 'Es gibt Hinweise auf eine aktive Störung, Schutzabschaltung oder einen kritischen Befund.'
      : hasDetectedErrorCode || hasHistoricalError
        ? 'Fehlerbild oder Störhistorie erkannt, aktuell aber nicht zwingend als akute Abschaltung bestätigt.'
        : 'Im gewählten Zeitraum wurde kein dominanter akuter Störhinweis erkannt.',
    tone: hasActiveError || hasCriticalFinding || normalizedStatus.includes('kritisch')
      ? 'critical'
      : hasDetectedErrorCode || hasHighFinding || normalizedStatus.includes('auffällig') || hasHistoricalError
        ? 'attention'
        : 'stable',
    icon: 'function',
  };

  const heatItem: SnapshotItem = {
    label: 'Wärmeabgabe',
    value: hasHeatTopic && (hasActiveError || hasCriticalFinding)
      ? 'Wärmeversorgung prüfen'
      : hasHeatTopic || hasHydraulicTopic || hasSensorTopic || hasCyclingTopic
        ? 'Wärmeabgabe beobachten'
        : 'Keine Versorgungsunterbrechung erkannt',
    detail: hasHeatTopic
      ? 'Heizleistung, Warmwasser und die zugehörigen Freigaben sollten im Einsatz zuerst gegengeprüft werden.'
      : hasHydraulicTopic || hasSensorTopic || hasCyclingTopic
        ? 'Die Anlage läuft nicht eindeutig fehlerfrei. Vorlauf, Rücklauf, Sensorik und Regelung mitprüfen.'
        : 'Die Daten zeigen keinen klaren Hinweis auf einen aktuellen Abbruch der Wärmeversorgung.',
    tone: hasHeatTopic && (hasActiveError || hasCriticalFinding)
      ? 'critical'
      : hasHeatTopic || hasHydraulicTopic || hasSensorTopic || hasCyclingTopic
        ? 'attention'
        : 'neutral',
    icon: 'heat',
  };

  const urgencyItem: SnapshotItem = {
    label: 'Einsatzstatus',
    value: getPriorityLabel(analysisResult),
    detail: quickChecks[0]
      ? `Mit diesem Schritt starten: ${quickChecks[0]}`
      : 'Noch kein konkreter Prüfschritt aus der Auswertung abgeleitet.',
    tone: hasActiveError || hasCriticalFinding
      ? 'critical'
      : hasDetectedErrorCode || hasHighFinding
        ? 'attention'
        : 'neutral',
    icon: 'urgency',
  };

  const workbenchItem: SnapshotItem = {
    label: 'Zuerst ansehen',
    value: getWorkbenchFocus(selectedIssue),
    detail: primarySeenWindow
      ? `Zeitbezug der Störspur: ${primarySeenWindow}`
      : 'Kein eindeutiger Fehlerzeitpunkt erkannt, daher vom Problembild aus in die passende Baugruppe einsteigen.',
    tone: 'neutral',
    icon: 'workbench',
  };

  return [functionItem, heatItem, urgencyItem, workbenchItem];
};

const getSpeechRecognitionErrorMessage = (error: string) => {
  switch (error) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Mikrofonzugriff wurde blockiert. Bitte Browserberechtigung freigeben.';
    case 'no-speech':
      return 'Keine Sprache erkannt. Bitte noch einmal sprechen.';
    case 'audio-capture':
      return 'Kein Mikrofon verfügbar oder das Gerät liefert kein Audiosignal.';
    case 'network':
      return 'Die Spracherkennung konnte keine Verbindung herstellen.';
    default:
      return 'Die Spracheingabe konnte nicht gestartet werden.';
  }
};

const AnalysisPage: React.FC = () => {
  const { user } = useAuthStore();
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const speechBaseNoteRef = useRef('');
  const speechTargetRef = useRef<SpeechTarget | null>(null);
  const shouldAutoSendChatRef = useRef(false);
  const chatDraftRef = useRef('');

  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [selectedRange, setSelectedRange] = useState('24h');
  const [selectedIssue, setSelectedIssue] = useState('quick-check');
  const [problemNote, setProblemNote] = useState('');
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [deepAnalysisResult, setDeepAnalysisResult] = useState<DeepAnalysisResponse | null>(null);
  const [showDetailedResults, setShowDetailedResults] = useState(false);
  const [showErrorAnalysisInfo, setShowErrorAnalysisInfo] = useState(false);
  const [showDeepAnalysisModal, setShowDeepAnalysisModal] = useState(false);
  const [manufacturer, setManufacturer] = useState('');
  const [heatPumpType, setHeatPumpType] = useState('');
  const [formError, setFormError] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  const speechRecognitionApi = typeof window !== 'undefined'
    ? window.SpeechRecognition ?? window.webkitSpeechRecognition
    : undefined;
  const speechSupported = Boolean(speechRecognitionApi);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  useEffect(() => {
    chatDraftRef.current = chatInput;
  }, [chatInput]);

  // 2. Load Devices
  const { data: devices, isLoading: isDevicesLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const resp = await api.get<Device[]>('/devices/');
      return resp.data;
    },
    enabled: !!user,
  });

  // 3. Analysis Mutation
  const analysisMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDeviceId) return null;

      const fromDate = getRangeStartDate(selectedRange);

      const response = await api.post<AnalysisResponse>(`/analysis/${selectedDeviceId}`, {
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        analysis_focus: buildAnalysisFocus(selectedIssue, problemNote),
        language: "de"
      });
      return response.data;
    },
    onSuccess: (data) => {
      setAnalysisResult(data);
      setShowDetailedResults(false);
      setShowErrorAnalysisInfo(Boolean(data?.should_trigger_error_analysis));
      if (data) {
        setChatMessages([
          createChatMessage(
            'assistant',
            buildAssistantChatMessage(data),
            'Erstantwort aus dem Schnellcheck',
          ),
        ]);
        setChatInput('');
      }
    }
  });

  const handleStartAnalysis = () => {
    recognitionRef.current?.stop();
    speechTargetRef.current = null;
    setSpeechError('');
    setAnalysisResult(null);
    setDeepAnalysisResult(null);
    setShowDetailedResults(false);
    setShowErrorAnalysisInfo(false);
    setChatMessages([]);
    setChatInput('');
    analysisMutation.mutate();
  };

  // 4. Deep Analysis Mutation
  const deepAnalysisMutation = useMutation({
    mutationFn: async ({ manufacturer, heat_pump_type }: { manufacturer: string, heat_pump_type: string }) => {
      if (!selectedDeviceId) return null;

      const fromDate = getRangeStartDate(selectedRange, true);

      const response = await api.post<DeepAnalysisResponse>(`/analysis/${selectedDeviceId}/deep`, {
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        analysis_focus: buildDeepAnalysisFocus(selectedIssue, problemNote),
        language: "de",
        manufacturer,
        heat_pump_type
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data) {
        setDeepAnalysisResult(data);
        setShowDetailedResults(true);
        setShowErrorAnalysisInfo(false);
        setShowDeepAnalysisModal(false);
      }
    }
  });

  const handleStartDeepAnalysis = () => {
    if (!manufacturer.trim() || !heatPumpType.trim()) {
      setFormError('Bitte füllen Sie beide Pflichtfelder aus.');
      return;
    }
    setFormError('');
    deepAnalysisMutation.mutate({ 
      manufacturer: manufacturer.trim(), 
      heat_pump_type: heatPumpType.trim() 
    });
  };

  const openDeepAnalysisModal = () => {
    setFormError('');
    setShowDeepAnalysisModal(true);
  };

  const handleSendChatMessage = (messageOverride?: string) => {
    const trimmedMessage = (messageOverride ?? chatDraftRef.current).trim();
    if (!trimmedMessage || !analysisResult || chatMutation.isPending) {
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

  const startSpeechInput = (target: SpeechTarget, autoSendOnEnd = false) => {
    if (!speechRecognitionApi) {
      setSpeechError('Dieser Browser unterstützt keine Spracheingabe. Empfohlen: aktuelles Chrome oder Edge.');
      return;
    }

    if (isListening && speechTargetRef.current === target) {
      return;
    }

    if (isListening && speechTargetRef.current && speechTargetRef.current !== target) {
      recognitionRef.current?.stop();
      setSpeechError('Die laufende Aufnahme wurde beendet. Bitte den Mikrofon-Button erneut für das gewünschte Feld drücken.');
      return;
    }

    speechBaseNoteRef.current = (target === 'note' ? problemNote : chatInput).trim();
    speechTargetRef.current = target;
  shouldAutoSendChatRef.current = target === 'chat' && autoSendOnEnd;
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

      const mergedText = [speechBaseNoteRef.current, transcript].filter(Boolean).join(' ').trim();
      if (speechTargetRef.current === 'chat') {
        setChatInput(mergedText);
        chatDraftRef.current = mergedText;
      } else {
        setProblemNote(mergedText);
      }
    };

    recognition.onerror = (event) => {
      setSpeechError(getSpeechRecognitionErrorMessage(event.error));
      setIsListening(false);
      shouldAutoSendChatRef.current = false;
      speechTargetRef.current = null;
    };

    recognition.onend = () => {
      setIsListening(false);
      const shouldAutoSend = shouldAutoSendChatRef.current;
      const activeTarget = speechTargetRef.current;
      shouldAutoSendChatRef.current = false;
      speechTargetRef.current = null;

      if (activeTarget === 'chat' && shouldAutoSend) {
        handleSendChatMessage(chatDraftRef.current);
      }
    };

    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  };

  const stopSpeechInput = (target?: SpeechTarget) => {
    if (!isListening) {
      return;
    }

    if (target && speechTargetRef.current !== target) {
      return;
    }

    recognitionRef.current?.stop();
  };

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      if (!selectedDeviceId) {
        return null;
      }

      const fromDate = getRangeStartDate(selectedRange);
      const response = await api.post<AnalysisResponse>(`/analysis/${selectedDeviceId}`, {
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        analysis_focus: buildChatAnalysisFocus(selectedIssue, problemNote, chatMessages, message, analysisResult),
        language: 'de',
      });

      return response.data;
    },
    onSuccess: (data) => {
      if (!data) {
        return;
      }

      setChatMessages((current) => [
        ...current,
        createChatMessage('assistant', buildAssistantChatMessage(data), 'Antwort aus dem Einsatz-Chat'),
      ]);
      setSpeechError('');
    },
    onError: (error) => {
      setChatMessages((current) => [
        ...current,
        createChatMessage(
          'assistant',
          getApiErrorMessage(error, 'Die Chat-Antwort konnte nicht erzeugt werden.'),
          'Fehler',
        ),
      ]);
    },
  });

  const analysisErrorMessage = getApiErrorMessage(
    analysisMutation.error,
    'Leider konnte die Analyse nicht durchgeführt werden.',
  );
  const deepAnalysisErrorMessage = getApiErrorMessage(
    deepAnalysisMutation.error,
    'Fehler bei der vertieften Analyse. Bitte erneut versuchen.',
  );
  const primarySignal = analysisResult ? getPrimarySignal(analysisResult, deepAnalysisResult) : null;
  const quickChecks = analysisResult ? getQuickChecks(analysisResult, deepAnalysisResult) : [];
  const snapshotItems = analysisResult ? getQuickSnapshotItems(analysisResult, deepAnalysisResult, selectedIssue, quickChecks) : [];
  const issueLabel = ISSUE_OPTIONS.find((option) => option.value === selectedIssue)?.label ?? 'Allgemeiner Schnellcheck';
  const primaryErrorWindow = analysisResult?.detected_error_codes[0]
    ? formatDetectedErrorSeenWindow(analysisResult.detected_error_codes[0])
    : null;

  const getSnapshotIcon = (icon: SnapshotItem['icon']) => {
    switch (icon) {
      case 'function':
        return <Siren className="w-4 h-4 text-white" />;
      case 'heat':
        return <Thermometer className="w-4 h-4 text-white" />;
      case 'urgency':
        return <Clock3 className="w-4 h-4 text-white" />;
      default:
        return <Wrench className="w-4 h-4 text-white" />;
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'high': return <AlertTriangle className="w-5 h-5 text-orange-500" />;
      case 'medium': return <Info className="w-5 h-5 text-blue-500" />;
      default: return <Info className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Modal for Deep Analysis Data */}
      {showDeepAnalysisModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-100 flex items-center gap-4 bg-slate-50">
              <div className="bg-orange-100 p-2 rounded-lg text-orange-600">
                <Stethoscope className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">Vertiefte Analyse vorbereiten</h3>
                <p className="text-xs text-slate-500">Bitte geben Sie Gerätedetails an</p>
              </div>
            </div>
            
            <div className="p-6 space-y-5">
              <div className="space-y-1.5">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                  Hersteller <span className="text-red-500">*</span>
                </label>
                <input 
                  type="text"
                  placeholder="z.B. Viessmann, Vaillant, Wolf..."
                  value={manufacturer}
                  onChange={(e) => setManufacturer(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition text-sm"
                />
                <p className="text-[10px] text-slate-400 italic">Hilft bei der Interpretation herstellerspezifischer Fehlercodes.</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                  Wärmepumpentyp <span className="text-red-500">*</span>
                </label>
                <input 
                  type="text"
                  placeholder="z.B. Vitocal 200-S, aroTHERM plus..."
                  value={heatPumpType}
                  onChange={(e) => setHeatPumpType(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition text-sm"
                />
                <p className="text-[10px] text-slate-400 italic">Ermöglicht den Abgleich mit bekannten Schwachstellen dieses Typs.</p>
              </div>

              {formError && (
                <div className="p-3 bg-red-50 border border-red-100 rounded-lg flex items-center gap-2 text-red-600 text-xs animate-in shake duration-300">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {formError}
                </div>
              )}

              {deepAnalysisMutation.isError && (
                <div className="p-3 bg-red-50 border border-red-100 rounded-lg flex items-center gap-2 text-red-600 text-xs">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {deepAnalysisErrorMessage}
                </div>
              )}
            </div>

            <div className="p-6 bg-slate-50 border-t border-slate-100 flex gap-3">
              <button 
                onClick={() => setShowDeepAnalysisModal(false)}
                className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 text-slate-600 text-sm font-bold hover:bg-white transition"
              >
                Abbrechen
              </button>
              <button 
                onClick={handleStartDeepAnalysis}
                disabled={deepAnalysisMutation.isPending}
                className="flex-[2] px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-bold hover:bg-blue-700 transition shadow-md shadow-blue-200 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deepAnalysisMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analysiere...
                  </>
                ) : (
                  <>
                    Vertiefte Analyse starten
                    <Brain className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header & Beta Info */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-8 text-white shadow-lg relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-white/20 p-2 rounded-lg backdrop-blur-sm">
              <Brain className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">KI-Schnellcheck (Beta)</h1>
              <p className="text-xs uppercase tracking-[0.2em] text-blue-100/80 mt-1">Für den Einsatz direkt beim Kunden</p>
            </div>
          </div>
          <p className="text-blue-100 max-w-2xl text-lg">
            Zeitraum wählen, Problem kurz eingrenzen und direkt die wahrscheinlichste Spur plus nächste Prüfschritte sehen.
          </p>
        </div>
        <Brain className="absolute right-[-20px] bottom-[-20px] w-64 h-64 text-white/10 rotate-12" />
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex gap-4 items-start">
        <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800">
          <p className="font-semibold mb-1 text-blue-900">Wichtiger Hinweis</p>
          Die KI liefert hier bewusst eine kurze Einsatzhilfe statt eines langen Berichts. Alle Ergebnisse bleiben datenbasierte Einschätzungen und ersetzen keine fachmännische Prüfung vor Ort.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Selection Area */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-6">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-3">1. Gerät auswählen</label>
              <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                {isDevicesLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-12 bg-slate-50 animate-pulse rounded-lg border border-slate-100"></div>
                  ))
                ) : devices?.length === 0 ? (
                  <p className="text-sm text-slate-500 italic p-4 text-center">Keine Geräte verfügbar</p>
                ) : (
                  devices?.map((device) => (
                    <button
                      key={device.id}
                      onClick={() => setSelectedDeviceId(device.id)}
                      className={`w-full flex items-center justify-between p-3 rounded-lg border transition text-left group ${
                        selectedDeviceId === device.id
                          ? 'bg-blue-50 border-blue-400 text-blue-700'
                          : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Activity className={`w-4 h-4 ${selectedDeviceId === device.id ? 'text-blue-500' : 'text-slate-400'}`} />
                        <div>
                          <p className="font-medium text-sm">{device.display_name}</p>
                          <p className="text-[10px] opacity-60 uppercase tracking-tighter">{device.slug}</p>
                        </div>
                      </div>
                      <ChevronRight className={`w-4 h-4 transition ${selectedDeviceId === device.id ? 'translate-x-1 opacity-100' : 'opacity-0'}`} />
                    </button>
                  ))
                )}
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-3">2. Zeitraum festlegen</label>
              <div className="grid grid-cols-3 gap-2">
                {TIME_RANGES.map((range) => (
                  <button
                    key={range.value}
                    onClick={() => setSelectedRange(range.value)}
                    className={`px-3 py-2 rounded-lg border text-xs font-medium transition ${
                      selectedRange === range.value
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-3">3. Problem eingrenzen</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2">
                  {ISSUE_OPTIONS.map((issue) => (
                    <button
                      key={issue.value}
                      onClick={() => setSelectedIssue(issue.value)}
                      className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                        selectedIssue === issue.value
                          ? 'bg-emerald-50 border-emerald-400 text-emerald-700'
                          : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      <p className="text-sm font-semibold">{issue.label}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Kurzer Hinweis optional</label>
                <div className="space-y-2">
                  <textarea
                    rows={4}
                    value={problemNote}
                    onChange={(e) => setProblemNote(e.target.value)}
                    placeholder="z. B. Kunde meldet keine Wärme seit heute Morgen, Fehlercode im Display, hohe Taktung..."
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-[11px] text-slate-500">
                      Spracheingabe für Monteur-Notizen: kurz sprechen, Text wird direkt in das Hinweisfeld übernommen.
                    </div>
                    <button
                      type="button"
                      onClick={() => (isListening && speechTargetRef.current === 'note' ? stopSpeechInput('note') : startSpeechInput('note'))}
                      disabled={!speechSupported && !isListening}
                      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${
                        isListening && speechTargetRef.current === 'note'
                          ? 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'
                          : 'bg-slate-100 text-slate-700 border border-slate-200 hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed'
                      }`}
                    >
                      {isListening && speechTargetRef.current === 'note' ? (
                        <>
                          <Square className="w-3.5 h-3.5" />
                          Aufnahme stoppen
                        </>
                      ) : (
                        <>
                          <Mic className="w-3.5 h-3.5" />
                          Spracheingabe starten
                        </>
                      )}
                    </button>
                  </div>
                  {!speechSupported && (
                    <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                      Spracheingabe ist nur in Browsern mit Web-Speech-Unterstützung verfügbar, typischerweise Chrome oder Edge.
                    </p>
                  )}
                  {speechError && (
                    <p className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                      {speechError}
                    </p>
                  )}
                </div>
              </div>
            </div>

            <button
              onClick={handleStartAnalysis}
              disabled={!selectedDeviceId || analysisMutation.isPending}
              className={`w-full py-4 rounded-xl font-bold flex items-center justify-center gap-3 transition shadow-sm ${
                !selectedDeviceId || analysisMutation.isPending
                  ? 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
                  : 'bg-blue-600 text-white hover:bg-blue-700 active:scale-[0.98]'
              }`}
            >
              {analysisMutation.isPending ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Analysiere Daten...
                </>
              ) : (
                <>
                  <Brain className="w-5 h-5" />
                  Schnellcheck starten
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results Area */}
        <div className="lg:col-span-2 space-y-6">
          {!analysisResult && !analysisMutation.isPending && !analysisMutation.isError && (
            <div className="bg-white border-2 border-dashed border-slate-200 rounded-2xl h-[500px] flex flex-col items-center justify-center text-slate-400 p-8 text-center">
              <div className="bg-slate-50 p-6 rounded-full mb-6">
                <Brain className="w-12 h-12 text-slate-300" />
              </div>
              <h3 className="text-xl font-bold text-slate-600 mb-2">Bereit für den Schnellcheck</h3>
              <p className="max-w-xs text-sm leading-relaxed">
                Wählen Sie links Gerät, Zeitraum und Problem. Rechts erscheint dann zuerst nur die kurze Antwort für den Einsatz vor Ort.
              </p>
            </div>
          )}

          {analysisMutation.isPending && (
            <div className="bg-white border border-slate-200 rounded-2xl h-[500px] flex flex-col items-center justify-center p-8 text-center space-y-6 animate-pulse">
              <div className="relative">
                <div className="absolute inset-0 bg-blue-400 blur-2xl opacity-20 animate-pulse"></div>
                <div className="relative bg-blue-50 p-6 rounded-full text-blue-600">
                  <Loader2 className="w-12 h-12 animate-spin" />
                </div>
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-800 mb-2">Die wahrscheinlichste Spur wird gesucht</h3>
                <p className="text-slate-500 text-sm max-w-sm">
                  Die KI wertet jetzt den gewählten Zeitraum aus und priorisiert eine kurze Antwort statt eines langen Berichts.
                </p>
              </div>
            </div>
          )}

          {analysisMutation.isError && (
            <div className="bg-white border border-red-200 rounded-2xl p-8 text-center space-y-4">
              <div className="mx-auto bg-red-50 p-4 rounded-full w-fit">
                <AlertCircle className="w-10 h-10 text-red-500" />
              </div>
              <h3 className="text-xl font-bold text-slate-800">Analyse fehlgeschlagen</h3>
              <p className="text-slate-600 text-sm max-w-md mx-auto">
                {analysisErrorMessage}
              </p>
              <button 
                onClick={handleStartAnalysis}
                className="text-blue-600 font-semibold hover:underline"
              >
                Erneut versuchen
              </button>
            </div>
          )}

          {analysisResult && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              {analysisResult.analysis_notice && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 items-start">
                  <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div className="text-sm text-amber-900">
                    <p className="font-semibold mb-1">Lokale Auswertung aktiv</p>
                    <p>{analysisResult.analysis_notice}</p>
                  </div>
                </div>
              )}

              <div className="bg-slate-900 rounded-2xl border border-slate-800 shadow-lg overflow-hidden text-white">
                <div className="p-6 md:p-8 space-y-6">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="bg-white/10 p-2 rounded-lg">
                        <Activity className="w-5 h-5" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold">{analysisResult.device_name}</h2>
                        <div className="flex items-center gap-2 text-xs text-slate-300 mt-0.5">
                          <Calendar className="w-3 h-3" />
                          <span>{new Date(analysisResult.from).toLocaleString()} - {new Date(analysisResult.to).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 max-w-sm">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">Betriebsstatus</p>
                      <p className="text-sm font-semibold text-white mt-1">{snapshotItems[0]?.value ?? 'Noch keine Einordnung'}</p>
                      <p className="text-xs text-slate-300 mt-1 leading-relaxed">{snapshotItems[0]?.detail}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-300 mb-2">Kurzantwort</p>
                      <p className="text-sm leading-relaxed text-slate-100">{analysisResult.summary}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-300 mb-2">Wichtigste Spur</p>
                      <p className="text-sm font-semibold text-white">{primarySignal?.title}</p>
                      <p className="text-sm leading-relaxed text-slate-200 mt-2">{primarySignal?.description}</p>
                    </div>
                  </div>

                  <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-5">
                    <div className="flex items-center gap-2 text-emerald-200 mb-3">
                      <CheckCircle2 className="w-4 h-4" />
                      <p className="text-sm font-bold">Nächste Schritte vor Ort</p>
                    </div>
                    <div className="space-y-3">
                      {quickChecks.length > 0 ? (
                        quickChecks.map((check, idx) => (
                          <div key={idx} className="flex items-start gap-3 text-sm text-emerald-50">
                            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-white/10 text-xs font-bold shrink-0">
                              {idx + 1}
                            </span>
                            <span>{check}</span>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-emerald-100/80">Keine konkreten Prüfschritte verfügbar.</p>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 xl:grid-cols-[1.45fr_1fr] gap-4">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
                      <div className="flex items-center justify-between gap-3 mb-4">
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-slate-300">Schnellbild</p>
                          <p className="text-sm font-bold text-white mt-1">Was der Heizungsbauer sofort wissen muss</p>
                        </div>
                        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold text-slate-200">
                          Für Heizungsbauer gedacht
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {snapshotItems.map((item) => {
                          const toneClasses = getSnapshotToneClasses(item.tone);
                          return (
                            <div key={item.label} className={`rounded-xl border p-4 ${toneClasses}`}>
                              <div className="flex items-center gap-3">
                                <div className="rounded-lg bg-slate-900/40 p-2">
                                  {getSnapshotIcon(item.icon)}
                                </div>
                                <div>
                                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">{item.label}</p>
                                  <p className="text-sm font-semibold text-white mt-1">{item.value}</p>
                                </div>
                              </div>
                              <p className="text-xs leading-relaxed mt-3 text-slate-200">{item.detail}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div className="rounded-xl border border-sky-300/15 bg-sky-400/10 p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-sky-100/70">Was Ich Vor Ort Wissen Will</p>
                      <p className="text-sm font-bold text-white mt-1">Monteur-Fokus</p>

                      <div className="space-y-3 mt-4">
                        <div className="rounded-xl border border-white/10 bg-slate-950/30 p-4">
                          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">Problembild</p>
                          <p className="text-sm font-semibold text-white mt-2">{issueLabel}</p>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-slate-950/30 p-4">
                          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">Baugruppe zuerst</p>
                          <p className="text-sm font-semibold text-white mt-2">{getWorkbenchFocus(selectedIssue)}</p>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-slate-950/30 p-4">
                          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">Fehler zuletzt gesehen</p>
                          <p className="text-sm font-semibold text-white mt-2">
                            {primaryErrorWindow ?? 'Noch kein konkreter Fehlerzeitpunkt erkannt'}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {analysisResult.detected_error_codes && analysisResult.detected_error_codes.length > 0 && (
                    <div className="rounded-xl border border-red-400/20 bg-red-500/10 p-5">
                      <div className="flex items-center gap-2 text-red-200 mb-3">
                        <Flag className="w-4 h-4" />
                        <p className="text-sm font-bold">Erkannte Fehlercodes</p>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {analysisResult.detected_error_codes.slice(0, 4).map((err, idx) => (
                          <div key={idx} className="rounded-lg border border-red-400/20 bg-slate-950/40 p-4">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="px-2 py-0.5 bg-red-600 text-white text-[10px] font-black rounded uppercase tracking-widest">Code {err.code}</span>
                              <span className="text-[10px] font-bold text-red-100/70 truncate">{err.source_label}</span>
                            </div>
                            <p className="text-sm font-bold text-white">{err.label}</p>
                            <p className="text-xs text-red-100/80 mt-2 font-mono">{err.observed_value}</p>
                            {formatDetectedErrorSeenWindow(err) && (
                              <p className="text-[11px] text-red-100/80 mt-3 leading-relaxed">
                                {formatDetectedErrorSeenWindow(err)}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between gap-4 bg-white border border-slate-200 rounded-xl p-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Technische Details nur bei Bedarf</p>
                  <p className="text-xs text-slate-500 mt-1">Die ausführliche Fehleranalyse bleibt standardmäßig eingeklappt.</p>
                </div>
                <button
                  onClick={() => setShowDetailedResults((current) => !current)}
                  className="px-4 py-2 rounded-lg border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  {showDetailedResults ? 'Details ausblenden' : 'Details anzeigen'}
                </button>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                <div className="p-5 md:p-6 border-b border-slate-100 bg-slate-50">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div className="flex items-center gap-3">
                      <div className="bg-slate-900 text-white p-2.5 rounded-xl">
                        <MessageSquareText className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-slate-900">Einsatz-Chat</h3>
                        <p className="text-sm text-slate-500">Folgefragen per Text oder Mikrofon stellen, Antwort kommt in kurzer Monteur-Sprache.</p>
                      </div>
                    </div>
                    <div className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600">
                      Live-Transkript + KI-Antwort
                    </div>
                  </div>
                </div>

                <div className="p-5 md:p-6 space-y-4">
                  <div className="max-h-[420px] overflow-y-auto space-y-3 pr-1">
                    {chatMessages.length > 0 ? (
                      chatMessages.map((message) => (
                        <div
                          key={message.id}
                          className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                          <div
                            className={`max-w-[90%] rounded-2xl px-4 py-3 shadow-sm border ${
                              message.role === 'user'
                                ? 'bg-blue-600 text-white border-blue-600'
                                : 'bg-slate-50 text-slate-800 border-slate-200'
                            }`}
                          >
                            {message.meta && (
                              <p
                                className={`text-[10px] font-semibold uppercase tracking-[0.16em] mb-2 ${
                                  message.role === 'user' ? 'text-blue-100' : 'text-slate-500'
                                }`}
                              >
                                {message.meta}
                              </p>
                            )}
                            <p className="text-sm leading-relaxed whitespace-pre-line">{message.content}</p>
                            <p
                              className={`text-[10px] mt-2 ${
                                message.role === 'user' ? 'text-blue-100/80' : 'text-slate-400'
                              }`}
                            >
                              {new Date(message.createdAt).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                            </p>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500">
                        Nach dem Schnellcheck kannst du hier Rückfragen stellen, zum Beispiel: "Ist das eher Sensorik oder Hydraulik?" oder "Womit starte ich am Gerät?"
                      </div>
                    )}

                    {chatMutation.isPending && (
                      <div className="flex justify-start">
                        <div className="max-w-[90%] rounded-2xl px-4 py-3 shadow-sm border bg-slate-50 text-slate-800 border-slate-200">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] mb-2 text-slate-500">Assistent denkt</p>
                          <div className="flex items-center gap-2 text-sm text-slate-500">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Die nächste Monteur-Antwort wird erzeugt...
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 space-y-3">
                    <textarea
                      rows={3}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSendChatMessage();
                        }
                      }}
                      placeholder="Frage an die KI, z. B. 'Ist der Fehler eher hydraulisch oder elektrisch?'"
                      className="w-full rounded-xl border border-white bg-white px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />

                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div className="text-[11px] text-slate-500">
                        Mit `Enter` senden, mit `Shift + Enter` Zeilenumbruch. Mikrofon gedrückt halten, sprechen, loslassen: dann wird automatisch gesendet.
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onPointerDown={(e) => {
                            e.preventDefault();
                            startSpeechInput('chat', true);
                          }}
                          onPointerUp={(e) => {
                            e.preventDefault();
                            stopSpeechInput('chat');
                          }}
                          onPointerLeave={() => {
                            stopSpeechInput('chat');
                          }}
                          onPointerCancel={() => {
                            stopSpeechInput('chat');
                          }}
                          disabled={!speechSupported && !isListening}
                          title={isListening && speechTargetRef.current === 'chat' ? 'Spracheingabe läuft' : 'Zum Sprechen gedrückt halten'}
                          aria-label={isListening && speechTargetRef.current === 'chat' ? 'Spracheingabe läuft' : 'Zum Sprechen gedrückt halten'}
                          className={`inline-flex h-11 w-11 items-center justify-center rounded-full border transition select-none touch-none ${
                            isListening && speechTargetRef.current === 'chat'
                              ? 'bg-red-50 text-red-700 border-red-200 shadow-inner scale-95'
                              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed'
                          }`}
                        >
                          {isListening && speechTargetRef.current === 'chat' ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                        </button>

                        <button
                          type="button"
                          onClick={() => handleSendChatMessage()}
                          disabled={!chatInput.trim() || chatMutation.isPending}
                          className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <SendHorizontal className="w-3.5 h-3.5" />
                          Senden
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {showDetailedResults && (
                <>
              {/* Summary Header */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-6 md:p-8 space-y-6">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="bg-blue-600 p-2 rounded-lg text-white">
                        <Activity className="w-5 h-5" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-slate-900">{analysisResult.device_name}</h2>
                        <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                          <Calendar className="w-3 h-3" />
                          <span>{new Date(analysisResult.from).toLocaleString()} - {new Date(analysisResult.to).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 max-w-sm">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Betriebsstatus</p>
                      <p className="text-sm font-semibold text-slate-900 mt-1">{snapshotItems[0]?.value ?? 'Noch keine Einordnung'}</p>
                      <p className="text-xs text-slate-600 mt-1 leading-relaxed">{snapshotItems[0]?.detail}</p>
                    </div>
                  </div>

                  <div className="bg-slate-50 rounded-xl p-6 border border-slate-100 relative">
                    <p className="text-slate-700 italic leading-relaxed">
                      "{analysisResult.summary}"
                    </p>
                    <span className="absolute -top-3 left-4 bg-white px-2 py-0.5 text-[10px] font-bold text-slate-400 border border-slate-200 rounded-md uppercase tracking-wider">
                      Zusammenfassung
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Error Codes (High Priority) */}
                {analysisResult.detected_error_codes && analysisResult.detected_error_codes.length > 0 && (
                  <div className="md:col-span-2 space-y-4">
                    <h3 className="font-bold text-red-700 flex items-center gap-2 px-1">
                      <Flag className="w-5 h-5 text-red-600" />
                      Identifizierte Fehler- & Alarmcodes
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {analysisResult.detected_error_codes.map((err, idx) => (
                        <div key={idx} className="bg-red-50 border border-red-200 rounded-xl p-4 shadow-sm relative overflow-hidden group">
                          <div className="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition">
                            <AlertCircle className="w-12 h-12 text-red-900" />
                          </div>
                          <div className="relative z-10">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="px-2 py-0.5 bg-red-600 text-white text-[10px] font-black rounded uppercase tracking-widest">Code {err.code}</span>
                              <span className="text-[10px] font-bold text-red-800/60 truncate">{err.source_label}</span>
                            </div>
                            <p className="text-sm font-bold text-red-900 mb-1">{err.label}</p>
                            <p className="text-xs text-red-700/80 bg-white/50 p-2 rounded border border-red-100 mt-2 font-mono">
                              {err.observed_value}
                            </p>
                            {formatDetectedErrorSeenWindow(err) && (
                              <p className="text-[11px] text-red-900/70 mt-3 leading-relaxed">
                                {formatDetectedErrorSeenWindow(err)}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Findings */}
                <div className="space-y-4">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2 px-1">
                    <Brain className="w-4 h-4 text-blue-500" />
                    Erkenntnisse & Befunde
                  </h3>
                  {analysisResult.findings.map((finding, idx) => (
                    <div key={idx} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <h4 className="font-bold text-slate-900 leading-tight">{finding.title}</h4>
                        {getSeverityIcon(finding.severity)}
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{finding.description}</p>
                      {finding.evidence.length > 0 && (
                        <div className="pt-2 border-t border-slate-50">
                           <ul className="space-y-1">
                             {finding.evidence.map((ev, eidx) => (
                               <li key={eidx} className="flex gap-2 items-start text-[10px] text-slate-500">
                                 <div className="w-1 h-1 rounded-full bg-slate-300 mt-1.5 shrink-0"></div>
                                 {ev}
                               </li>
                             ))}
                           </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Hints & Optimization */}
                <div className="space-y-6">
                  {analysisResult.anomalies.length > 0 && (
                    <div className="space-y-4">
                      <h3 className="font-bold text-slate-800 flex items-center gap-2 px-1">
                        <AlertTriangle className="w-4 h-4 text-orange-500" />
                        Auffälligkeiten
                      </h3>
                      <div className="bg-orange-50 border border-orange-100 rounded-xl overflow-hidden">
                        {analysisResult.anomalies.map((anomaly, idx) => (
                          <div key={idx} className="p-4 border-b border-orange-100 last:border-0">
                            <h4 className="text-sm font-bold text-orange-900 mb-1">{anomaly.title}</h4>
                            <p className="text-xs text-orange-800/80">{anomaly.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="space-y-4">
                    <h3 className="font-bold text-slate-800 flex items-center gap-2 px-1">
                      <Lightbulb className="w-4 h-4 text-blue-500" />
                      Optimierungshinweise
                    </h3>
                    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                      <ul className="space-y-3">
                        {analysisResult.optimization_hints.map((hint, idx) => (
                          <li key={idx} className="flex gap-3 items-start group">
                            <div className="p-1 bg-blue-50 rounded text-blue-600 mt-0.5 group-hover:bg-blue-100 transition">
                              <CheckCircle2 className="w-3 h-3" />
                            </div>
                            <span className="text-sm text-slate-600">{hint}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <h3 className="font-bold text-slate-800 flex items-center gap-2 px-1">
                      <Stethoscope className="w-4 h-4 text-indigo-500" />
                      Empfohlene Prüfungen
                    </h3>
                    <div className="bg-slate-900 rounded-xl p-5 text-indigo-100 shadow-inner">
                      <ul className="space-y-3">
                        {analysisResult.recommended_followup_checks.map((check, idx) => (
                          <li key={idx} className="flex gap-3 items-start">
                            <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-2 shrink-0"></div>
                            <span className="text-sm">{check}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              {/* Error Analysis Notification */}
              {showErrorAnalysisInfo && !deepAnalysisResult && (
                <div className="mb-6 bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
                  <ShieldCheck className="w-5 h-5 text-indigo-600 mt-0.5" />
                  <div className="flex-1">
                    <h5 className="text-sm font-bold text-indigo-900">Vertiefte Fehleranalyse starten</h5>
                    <p className="text-xs text-indigo-800 mt-1">
                      Die vertiefte Analyse führt eine detaillierte Ursachenforschung durch und interpretiert Fehlercodes über einen Zeitraum von 7 Tagen.
                    </p>
                    <button 
                      onClick={openDeepAnalysisModal}
                      disabled={deepAnalysisMutation.isPending}
                      className="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 transition flex items-center gap-2"
                    >
                      {deepAnalysisMutation.isPending ? (
                        <>
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Analysiere...
                        </>
                      ) : (
                        <>
                          <Brain className="w-3 h-3" />
                          Jetzt tiefen-analysieren
                        </>
                      )}
                    </button>
                  </div>
                  <button 
                    onClick={() => setShowErrorAnalysisInfo(false)}
                    className="text-indigo-400 hover:text-indigo-600 transition"
                  >
                    <ChevronRight className="w-4 h-4 rotate-90" />
                  </button>
                </div>
              )}

              {/* Deep Analysis Result */}
              {deepAnalysisResult && (
                <div className="mb-6 bg-slate-900 rounded-2xl border border-slate-800 shadow-xl overflow-hidden animate-in zoom-in-95 duration-500">
                  <div className="p-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
                  <div className="p-6 md:p-8 space-y-8">
                    {deepAnalysisResult.analysis_notice && (
                      <div className="bg-amber-500/10 border border-amber-400/20 rounded-xl p-4 flex items-start gap-3">
                        <Info className="w-5 h-5 text-amber-300 shrink-0 mt-0.5" />
                        <div className="text-sm text-amber-100">
                          <p className="font-semibold mb-1">Lokale Tiefenanalyse aktiv</p>
                          <p>{deepAnalysisResult.analysis_notice}</p>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="bg-indigo-500/20 p-3 rounded-xl text-indigo-400 border border-indigo-500/30">
                          <Stethoscope className="w-6 h-6" />
                        </div>
                        <div>
                          <h3 className="text-xl font-bold text-white">Vertiefte Fehlerdiagnose</h3>
                          <p className="text-slate-400 text-xs">Technische KI-Expertise • {new Date(deepAnalysisResult.from).toLocaleDateString()} - {new Date(deepAnalysisResult.to).toLocaleDateString()}</p>
                        </div>
                      </div>
                      <div className="hidden md:block">
                        <div className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-full text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                          Deep Analysis v2
                        </div>
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-8">
                      <div className="space-y-6">
                        <div className="space-y-3">
                          <h4 className="text-indigo-400 font-bold text-sm flex items-center gap-2">
                            <Info className="w-4 h-4" />
                            Technische Zusammenfassung
                          </h4>
                          <p className="text-slate-300 text-sm leading-relaxed bg-slate-800/50 p-4 rounded-xl border border-slate-800">
                            {deepAnalysisResult.technical_summary}
                          </p>
                        </div>

                        <div className="space-y-4">
                          <h4 className="text-indigo-400 font-bold text-sm flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" />
                            Vermutete Ursachen
                          </h4>
                          <div className="space-y-2">
                            {deepAnalysisResult.suspected_causes.map((cause: string, idx: number) => (
                              <div key={idx} className="flex items-start gap-3 p-3 bg-red-500/5 border border-red-500/10 rounded-lg group hover:bg-red-500/10 transition">
                                <div className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1.5 shrink-0 shadow-[0_0_8px_rgba(239,68,68,0.5)]"></div>
                                <span className="text-slate-300 text-sm">{cause}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="space-y-6">
                        <div className="space-y-4">
                          <h4 className="text-emerald-400 font-bold text-sm flex items-center gap-2">
                            <ArrowRight className="w-4 h-4" />
                            Nächste Diagnoseschritte
                          </h4>
                          <div className="space-y-3">
                            {deepAnalysisResult.diagnostic_steps.map((step: string, idx: number) => (
                              <div key={idx} className="flex items-center gap-4 p-3 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
                                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold border border-emerald-500/30">
                                  {idx + 1}
                                </span>
                                <span className="text-slate-300 text-sm font-medium">{step}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="p-4 bg-indigo-500/5 border border-indigo-500/10 rounded-xl">
                          <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-widest mb-3">Technische Befunde</h4>
                          <div className="space-y-3">
                            {deepAnalysisResult.technical_findings.map((f: any, i: number) => (
                              <div key={i} className="text-xs">
                                <div className="font-bold text-slate-200">{f.title}</div>
                                <div className="text-slate-400 mt-1">{f.description}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="pt-6 border-t border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
                      <p className="text-[10px] text-slate-500 uppercase tracking-widest leading-relaxed text-center md:text-left">
                        {deepAnalysisResult.disclaimer}
                      </p>
                      <button 
                        onClick={() => setDeepAnalysisResult(null)}
                        className="text-xs text-slate-400 hover:text-white transition underline underline-offset-4"
                      >
                        Schließen
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Error Analysis Placeholder */}
              {analysisResult.should_trigger_error_analysis && !deepAnalysisResult && (
                <div className="bg-gradient-to-r from-orange-50 to-red-50 border border-orange-200 rounded-2xl p-6 flex flex-col md:flex-row items-center justify-between gap-6">
                  <div className="flex items-center gap-5">
                    <div className="bg-white p-3 rounded-xl border border-orange-200 shadow-sm text-orange-600">
                      <AlertCircle className="w-8 h-8" />
                    </div>
                    <div>
                      <h4 className="font-bold text-slate-900">Vertiefte Fehleranalyse empfohlen</h4>
                      <p className="text-sm text-slate-600 mt-1">
                        Aufgrund kritischer Muster schlägt das System eine detaillierte Ursachenforschung vor.
                      </p>
                    </div>
                  </div>
                  <button 
                    onClick={openDeepAnalysisModal}
                    className="flex items-center gap-2 px-6 py-3 bg-white border border-orange-200 rounded-xl text-orange-600 text-sm font-bold hover:bg-orange-50 hover:border-orange-300 transition-all shadow-sm active:scale-95"
                  >
                    Vertiefte Fehleranalyse starten
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              )}
                </>
              )}

              {/* Disclaimer */}
              <div className="text-[10px] text-slate-400 text-center uppercase tracking-widest pt-8 border-t border-slate-100">
                {analysisResult.disclaimer} • Vertrauen: {analysisResult.confidence}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AnalysisPage;
