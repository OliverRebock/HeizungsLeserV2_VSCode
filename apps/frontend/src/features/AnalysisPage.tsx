import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
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
  Flag
} from 'lucide-react';
import api from '../lib/api';
import { useAuthStore } from '../hooks/useAuth';
import type { Device, AnalysisResponse, DeepAnalysisResponse, Tenant } from '../types/api';

const TIME_RANGES = [
  { label: 'Letzte 24h', value: '24h' },
  { label: 'Letzte 7 Tage', value: '7d' },
  { label: 'Letzte 30 Tage', value: '30d' },
];

const AnalysisPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.is_superuser || user?.tenants?.some(t => t.role === 'platform_admin');

  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [selectedRange, setSelectedRange] = useState('24h');
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [deepAnalysisResult, setDeepAnalysisResult] = useState<DeepAnalysisResponse | null>(null);
  const [showErrorAnalysisInfo, setShowErrorAnalysisInfo] = useState(false);
  const [showDeepAnalysisModal, setShowDeepAnalysisModal] = useState(false);
  const [manufacturer, setManufacturer] = useState('');
  const [heatPumpType, setHeatPumpType] = useState('');
  const [formError, setFormError] = useState('');

  // 1. Load Tenants (only for Admin)
  const { data: tenants } = useQuery({
    queryKey: ['tenants'],
    queryFn: async () => {
      if (!isAdmin) return [];
      const response = await api.get<Tenant[]>('/tenants/');
      return response.data;
    },
    enabled: !!user && isAdmin,
  });

  // 2. Load Devices
  const { data: devices, isLoading: isDevicesLoading } = useQuery({
    queryKey: ['devices', tenants],
    queryFn: async () => {
      if (isAdmin && tenants) {
        const allDevices: Device[] = [];
        for (const tenant of tenants) {
          try {
            const resp = await api.get<Device[]>(`/devices/?tenant_id=${tenant.id}`);
            allDevices.push(...resp.data);
          } catch (e) {
            console.error(`Error loading devices for tenant ${tenant.id}`, e);
          }
        }
        return allDevices;
      } else {
        // For normal users, the API usually returns their devices without tenant_id filter if handled by backend
        // or we use the tenants from their user object.
        const allDevices: Device[] = [];
        for (const ut of user?.tenants || []) {
           try {
             const resp = await api.get<Device[]>(`/devices/?tenant_id=${ut.tenant_id}`);
             allDevices.push(...resp.data);
           } catch (e) {
             console.error(`Error loading devices for tenant ${ut.tenant_id}`, e);
           }
        }
        return allDevices;
      }
    },
    enabled: !!user,
  });

  // 3. Analysis Mutation
  const analysisMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDeviceId) return null;
      
      let fromDate = new Date();
      if (selectedRange === '24h') fromDate.setHours(fromDate.getHours() - 24);
      else if (selectedRange === '7d') fromDate.setDate(fromDate.getDate() - 7);
      else if (selectedRange === '30d') fromDate.setDate(fromDate.getDate() - 30);

      const response = await api.post<AnalysisResponse>(`/analysis/${selectedDeviceId}`, {
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        analysis_focus: "Gesamtzustand, Effizienz und Taktung",
        language: "de"
      });
      return response.data;
    },
    onSuccess: (data) => {
      setAnalysisResult(data);
      if (data && data.should_trigger_error_analysis) {
        setShowErrorAnalysisInfo(true);
      }
    }
  });

  const handleStartAnalysis = () => {
    setAnalysisResult(null);
    setDeepAnalysisResult(null);
    analysisMutation.mutate();
  };

  // 4. Deep Analysis Mutation
  const deepAnalysisMutation = useMutation({
    mutationFn: async ({ manufacturer, heat_pump_type }: { manufacturer: string, heat_pump_type: string }) => {
      if (!selectedDeviceId) return null;
      
      let fromDate = new Date();
      // Deep analysis usually needs a bit more context, so we take at least 7 days or the selected range
      if (selectedRange === '24h') fromDate.setDate(fromDate.getDate() - 7);
      else if (selectedRange === '7d') fromDate.setDate(fromDate.getDate() - 7);
      else if (selectedRange === '30d') fromDate.setDate(fromDate.getDate() - 30);

      const response = await api.post<DeepAnalysisResponse>(`/analysis/${selectedDeviceId}/deep`, {
        from: fromDate.toISOString(),
        to: new Date().toISOString(),
        analysis_focus: "Technische Fehlerdiagnose und Komponentenprüfung",
        language: "de",
        manufacturer,
        heat_pump_type
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data) {
        setDeepAnalysisResult(data);
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

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s.includes('kritisch')) return 'text-red-600 bg-red-50 border-red-200';
    if (s.includes('auffällig')) return 'text-orange-600 bg-orange-50 border-orange-200';
    if (s.includes('beobachtung')) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-green-600 bg-green-50 border-green-200';
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
                  Fehler bei der Analyse. Bitte erneut versuchen.
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
            <h1 className="text-3xl font-bold tracking-tight">KI-Analyse (Beta)</h1>
          </div>
          <p className="text-blue-100 max-w-2xl text-lg">
            Nutzen Sie künstliche Intelligenz, um Heizkurven, Taktverhalten und Effizienz Ihrer Geräte automatisiert auszuwerten.
          </p>
        </div>
        <Brain className="absolute right-[-20px] bottom-[-20px] w-64 h-64 text-white/10 rotate-12" />
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex gap-4 items-start">
        <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800">
          <p className="font-semibold mb-1 text-blue-900">Wichtiger Hinweis</p>
          Die KI-Analyse ist ein unterstützendes Werkzeug. Sie stellt keine endgültige Diagnose dar und ersetzt keine fachmännische Prüfung vor Ort. Alle Ergebnisse sind als datenbasierte Einschätzungen zu verstehen.
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
                  KI-Analyse starten
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
              <h3 className="text-xl font-bold text-slate-600 mb-2">Bereit zur Analyse</h3>
              <p className="max-w-xs text-sm leading-relaxed">
                Wählen Sie links ein Gerät und den Zeitraum aus, um eine automatisierte Auswertung zu starten.
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
                <h3 className="text-xl font-bold text-slate-800 mb-2">Daten werden verarbeitet</h3>
                <p className="text-slate-500 text-sm max-w-sm">
                  Die KI wertet nun alle verfügbaren Entitäten und Messreihen aus dem gewählten Zeitraum aus. Dies kann einige Sekunden dauern...
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
                Leider konnte die Analyse nicht durchgeführt werden. Möglicherweise fehlen Daten im gewählten Zeitraum oder der KI-Service ist derzeit nicht erreichbar.
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
                    <div className={`px-4 py-2 rounded-full border text-sm font-bold flex items-center gap-2 ${getStatusColor(analysisResult.overall_status)}`}>
                      <span className="w-2 h-2 rounded-full bg-current animate-pulse"></span>
                      {analysisResult.overall_status}
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
