import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { Device, Entity, DeviceDataResponse, Tenant, TimeSeries } from '../types/api';
import { 
  ArrowLeft, 
  Activity, 
  List, 
  BarChart3, 
  Search, 
  CheckCircle2,
  XCircle,
  Clock,
  Info,
  ChevronRight,
  Database,
  Layout,
  Plus,
  Star
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { DashboardService, type DashboardItem } from '../lib/dashboard';
import { ValueWidget, StatusWidget, MiniChartWidget } from '../components/DashboardWidgets';

const DeviceDetailPage: React.FC = () => {
  const { deviceId } = useParams<{ deviceId: string }>();
  const [activeTab, setActiveTab] = useState<'overview' | 'entities' | 'charts' | 'dashboard'>('overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [domainFilter, setDomainFilter] = useState<string>('all');
  const [kindFilter, setKindFilter] = useState<string>('all');
  const [chartableFilter, setChartableFilter] = useState<string>('all');
  const [selectedEntities, setSelectedEntities] = useState<string[]>([]);
  const [timeRange, setTimeRange] = useState<string>('24h');
  const [dashboardItems, setDashboardItems] = useState<DashboardItem[]>([]);
  const [selectedEntityForModal, setSelectedEntityForModal] = useState<Entity | null>(null);
  const [modalTimeRange, setModalTimeRange] = useState<string>('12h');

  // Load dashboard on deviceId change
  useEffect(() => {
    const loadDashboard = async () => {
      if (deviceId) {
        const items = await DashboardService.getDashboard(deviceId);
        setDashboardItems(items);
      }
    };
    loadDashboard();
  }, [deviceId]);

  // Device Info
  const { data: device, isLoading: isDeviceLoading, error: deviceError } = useQuery({
    queryKey: ['device', deviceId],
    queryFn: async () => {
      const response = await api.get<Device>(`/devices/${deviceId}`);
      return response.data;
    },
  });

  // Tenant Info (for Display)
  const { data: tenant } = useQuery({
    queryKey: ['tenant', device?.tenant_id],
    queryFn: async () => {
      if (!device?.tenant_id) return null;
      const response = await api.get<Tenant>(`/tenants/${device.tenant_id}`);
      return response.data;
    },
    enabled: !!device?.tenant_id,
  });

  // Entities
  const { data: entities, isLoading: isEntitiesLoading } = useQuery({
    queryKey: ['device-entities', deviceId],
    queryFn: async () => {
      const response = await api.get<Entity[]>(`/data/${deviceId}/entities`);
      return response.data;
    },
    enabled: !!deviceId,
  });

  // TimeSeries Data
  const { data: chartData, isLoading: isChartDataLoading } = useQuery({
    queryKey: ['device-data', deviceId, selectedEntities.sort().join(','), timeRange],
    queryFn: async () => {
      if (selectedEntities.length === 0) return null;
      const response = await api.get<DeviceDataResponse>(`/data/${deviceId}/timeseries`, {
        params: {
          entity_ids: selectedEntities.join(','),
          range: timeRange
        }
      });
      return response.data;
    },
    enabled: !!deviceId && selectedEntities.length > 0,
  });

  // TimeSeries Data for Modal
  const { data: modalChartData, isLoading: isModalChartLoading } = useQuery({
    queryKey: ['device-entity-data', deviceId, selectedEntityForModal?.entity_id, modalTimeRange],
    queryFn: async () => {
      if (!selectedEntityForModal) return null;
      const response = await api.get<DeviceDataResponse>(`/data/${deviceId}/timeseries`, {
        params: {
          entity_ids: selectedEntityForModal.entity_id,
          range: modalTimeRange
        }
      });
      return response.data;
    },
    enabled: !!deviceId && !!selectedEntityForModal,
  });

  const filteredEntities = entities?.filter(e => {
    const matchesSearch = (e.friendly_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.entity_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesDomain = domainFilter === 'all' || e.domain === domainFilter;
    const matchesKind = kindFilter === 'all' || e.data_kind === kindFilter;
    const matchesChartable = chartableFilter === 'all' || 
      (chartableFilter === 'yes' && e.chartable) || 
      (chartableFilter === 'no' && !e.chartable);
    
    return matchesSearch && matchesDomain && matchesKind && matchesChartable;
  });

  const domains = Array.from(new Set(entities?.map(e => e.domain) || [])).sort();
  const dataKinds = Array.from(new Set(entities?.map(e => e.data_kind) || [])).sort();

  const translateDataKind = (kind: string) => {
    const translations: Record<string, string> = {
      'numeric': 'Numerisch',
      'binary': 'Binär',
      'enum': 'Aufzählung',
      'string': 'Text'
    };
    return translations[kind] || kind;
  };

  const toggleEntity = (id: string) => {
    setSelectedEntities(prev => 
      prev.includes(id) ? prev.filter(e => e !== id) : [...prev, id]
    );
  };

  const toggleDashboard = async (entity: Entity) => {
    if (!deviceId) return;
    
    let type: 'value' | 'status' | 'mini-chart' = 'value';
    if (entity.data_kind === 'binary') type = 'status';
    else if (entity.chartable) type = 'mini-chart';

    const item: any = {
      id: entity.entity_id,
      title: entity.friendly_name || entity.entity_id,
      type
    };

    await DashboardService.toggleItem(deviceId, item);
    const updatedItems = await DashboardService.getDashboard(deviceId);
    setDashboardItems(updatedItems);
  };

  const removeFromDashboard = async (entityId: string) => {
    if (!deviceId) return;
    await DashboardService.removeItem(deviceId, entityId);
    const updatedItems = await DashboardService.getDashboard(deviceId);
    setDashboardItems(updatedItems);
  };

  const getModalChartOptions = () => {
    if (!modalChartData || !modalChartData.series || modalChartData.series.length === 0) return {};
    const s = modalChartData.series[0];
    const kind = s.data_kind;
    
    if (kind === 'numeric') {
      const unit = (s.meta && (s.meta as any).unit_of_measurement) || '';
      return numericOptions([s], unit);
    } else if (kind === 'binary') {
      return binaryOptions([s]);
    } else if (kind === 'enum') {
      return enumOptions(s);
    } else {
      return stringOptions(s);
    }
  };

  const getSeriesColor = (index: number) => {
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];
    return colors[index % colors.length];
  };

  // Neue Vergleichslogik: Panels je Datentyp/Einheit, synchronisierte Zeitachse
  const buildPanels = () => {
    const series: TimeSeries[] = (chartData?.series ?? []).filter(s => s && s.entity_id);

    console.log('Building Panels. Selected:', selectedEntities);
    console.log('Chart Data Series:', series);

    const numericGroups = new Map<string, TimeSeries[]>();
    const binaries: TimeSeries[] = [];
    const enums: TimeSeries[] = [];
    const strings: TimeSeries[] = [];

    // Priorität: Bekannte Heizungswerte (°C) in einer Gruppe, egal ob "C", "°C", "grad"
    const normalizeUnit = (u: string) => {
      if (!u) return '—';
      const upper = u.toUpperCase().trim();
      if (upper === '°C' || upper === 'C' || upper === 'GRAD' || upper === 'CELSIUS') return '°C';
      if (upper === '%' || upper === 'PROZENT') return '%';
      if (upper === 'BAR') return 'bar';
      if (upper === 'KW' || upper === 'W') return 'kW';
      return u;
    };

    series.forEach((s) => {
      // WICHTIG: Datentypen strikt trennen
      if (s.data_kind === 'numeric') {
        const unit = s.meta?.unit_of_measurement || (s.meta as any)?.unit || '';
        const key = normalizeUnit(unit);
        console.log(`Processing numeric entity: ${s.entity_id}, Unit: ${unit}, Normalized: ${key}`);
        
        // BUGFIX: Wenn das Backend (durch den vorherigen Komma-Bug) eine aggregierte Serie geliefert hat,
        // splitten wir sie hier nicht künstlich auf, sondern verlassen uns jetzt auf saubere Backend-Daten.
        if (!numericGroups.has(key)) numericGroups.set(key, []);
        numericGroups.get(key)!.push(s);
      } else if (s.data_kind === 'binary') {
        binaries.push(s);
      } else if (s.data_kind === 'enum') {
        // Enums werden nie in den numerischen Vergleich aufgenommen,
        // auch wenn sie eine Einheit wie °C haben.
        enums.push(s);
      } else if (s.data_kind === 'string') {
        strings.push(s);
      }
    });

    console.log('Numeric Groups:', Array.from(numericGroups.entries()));

    return { numericGroups, binaries, enums, strings };
  };

  const groupId = deviceId ? `device-${deviceId}-compare` : 'compare-group';

  const numericOptions = (seriesList: TimeSeries[], unitLabel: string) => {
    // Get range from the first series if available to keep X-axis clean
    const range = (chartData?.range) || (modalChartData?.range);
    const minTime = range?.from ? new Date(range.from).getTime() : undefined;
    const maxTime = range?.to ? new Date(range.to).getTime() : undefined;

    return {
      tooltip: { 
        trigger: 'axis', 
        axisPointer: { 
          type: 'cross',
          label: {
            backgroundColor: '#6a7985'
          }
        },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: { color: '#1e293b', fontSize: 12 },
        extraCssText: 'shadow-sm rounded-lg border border-slate-200 p-2',
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          let res = `<div class="font-bold text-slate-800 mb-1 border-b pb-1 border-slate-100">${params[0].axisValueLabel}</div>`;
          params.forEach((p: any) => {
            // Find serie by ID to be robust
            const s = seriesList.find(item => item.friendly_name === p.seriesName || item.entity_id === p.seriesId);
            const unit = s?.meta?.unit_of_measurement || unitLabel || '';
            const val = typeof p.data[1] === 'number' ? p.data[1].toLocaleString('de-DE', { maximumFractionDigits: 1 }) : p.data[1];
            res += `<div class="flex items-center justify-between gap-4 py-0.5">
                      <div class="flex items-center gap-2">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background-color:${p.color};"></span>
                        <span class="text-slate-600 font-medium">${p.seriesName}</span>
                      </div>
                      <span class="font-bold text-slate-900">${val} ${unit}</span>
                    </div>`;
          });
          return res;
        }
      },
      grid: { left: '3%', right: '3%', bottom: 30, top: 40, containLabel: true },
      legend: {
        show: true,
        top: 0,
        icon: 'circle',
        textStyle: { color: '#64748b', fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10
      },
      xAxis: { 
        type: 'time', 
        boundaryGap: false,
        min: minTime,
        max: maxTime,
        axisLabel: { 
          color: '#94a3b8', 
          fontSize: 10,
          formatter: (value: number) => {
            const date = new Date(value);
            return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
          }
        },
        axisLine: { lineStyle: { color: '#f1f5f9' } },
        splitLine: { show: true, lineStyle: { color: '#f8fafc' } },
      },
      yAxis: { 
        type: 'value', 
        scale: true, 
        min: (value: any) => {
          // Sicherstellen dass 0 immer Teil der Achse ist oder zumindest nah dran
          return value.min > 0 ? 0 : value.min;
        },
        name: unitLabel || undefined, 
        nameTextStyle: { color: '#94a3b8', fontSize: 10 },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } }
      },
      series: seriesList.map((s, idx) => {
        // Sort points by timestamp to ensure correct line drawing
        const sortedPoints = [...s.points].sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
        const seriesData = sortedPoints.map(p => [new Date(p.ts).getTime(), p.value ?? null]);
        console.log(`Series ${s.friendly_name} (${s.entity_id}) data points:`, seriesData.length);

        const color = getSeriesColor(idx);
        
        // Einheitlicher numerischer Stil auf Benutzerwunsch:
        // Ehrliche Darstellung ohne künstliche Glättung (smooth: false), 
        // um Artefakte/Verfälschungen am Rand zu vermeiden.
        return {
          id: s.entity_id,
          name: s.friendly_name,
          type: 'line',
          showSymbol: false, 
          symbolSize: 4,
          step: false, // Keine Stufen mehr fÃ¼r numerische Werte
          smooth: false, // DEAKTIVIERT: Ehrliche Rohdatenkurve statt künstlicher Artefakte
          connectNulls: false, // LÃ¼cken lassen, wenn keine Daten vorliegen
          lineStyle: { 
            width: 2.5, // Etwas feiner für ehrliche Darstellung
            color: color,
            opacity: 1
          },
          itemStyle: { color: color },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}25` },
              { offset: 1, color: `${color}00` }
            ])
          },
          markLine: {
            silent: true,
            symbol: 'none',
            label: { show: false },
            data: [{ yAxis: 0, lineStyle: { color: '#e2e8f0', type: 'dashed', width: 1 } }]
          },
          data: seriesData
        };
      })
    };
  };

  const binaryOptions = (seriesList: TimeSeries[]) => {
    // In Home Assistant, state history is shown as horizontal bars.
    // We achieve this by mapping each series to its own row.
    return {
      tooltip: { 
        trigger: 'axis', 
        axisPointer: { type: 'line', lineStyle: { color: 'rgba(0,0,0,0.05)', width: 1 } },
        backgroundColor: 'rgba(255, 255, 255, 0.98)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: { color: '#1e293b', fontSize: 12 },
        extraCssText: 'box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border-radius: 8px; padding: 10px;',
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          
          // Only show unique series in tooltip to avoid clutter
          const seen = new Set();
          let res = `<div class="font-bold text-slate-800 mb-2 border-b pb-1 border-slate-100">${params[0].axisValueLabel}</div>`;
          
          params.forEach((p: any) => {
            if (seen.has(p.seriesId)) return;
            seen.add(p.seriesId);
            
            // Check if this is the synthetic end point (carry forward)
            // We can detect this if the point's timestamp matches the series last point
            // and it's the very last data entry.
            const series = seriesList.find(s => s.entity_id === p.seriesId);
            const isSynthetic = series && series.points.length > 0 && 
                               new Date(series.points[series.points.length - 1].ts).getTime() === p.value[0] &&
                               p.dataIndex === series.points.length - 1;

            const val = p.data[1];
            const isAn = val === 1 || val === (p.seriesIndex + 1);
            const label = isAn ? 'An' : 'Aus';
            
            res += `<div class="flex items-center justify-between gap-6 py-0.5">
                      <div class="flex items-center gap-2">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background-color:${p.color};"></span>
                        <span class="text-slate-500 font-medium">${p.seriesName}${isSynthetic ? ' <span class="text-[10px] italic opacity-60">(aktuell)</span>' : ''}</span>
                      </div>
                      <span class="font-bold ${isAn ? 'text-blue-600' : 'text-slate-400'}">${label}</span>
                    </div>`;
          });
          return res;
        }
      },
      grid: { 
        left: 120, // Space for names on the left
        right: '3%', 
        bottom: 30, 
        top: 10, 
        containLabel: false 
      },
      xAxis: { 
        type: 'time', 
        boundaryGap: false,
        axisLabel: { 
          color: '#94a3b8', 
          fontSize: 10,
          formatter: (value: number) => {
            const date = new Date(value);
            return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
          }
        },
        axisLine: { show: false },
        splitLine: { show: true, lineStyle: { color: '#f8fafc' } }
      },
      yAxis: { 
        type: 'value',
        min: 0,
        max: seriesList.length,
        interval: 1,
        axisLabel: { 
          show: true,
          color: '#64748b',
          fontSize: 10,
          fontWeight: 600,
          formatter: (value: number) => {
            if (value <= 0 || value > seriesList.length) return '';
            const s = seriesList[seriesList.length - Math.round(value)];
            return s?.friendly_name || '';
          }
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { 
          show: true, 
          lineStyle: { color: '#f1f5f9', type: 'dashed' } 
        }
      },
      series: seriesList.map((s, idx) => {
        // We invert the index so the first entity is at the top
        const rowIdx = seriesList.length - idx;
        const color = getSeriesColor(idx);
        
        return {
          id: s.entity_id,
          name: s.friendly_name,
          type: 'line',
          step: 'end',
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 0 }, // Hide the line
          areaStyle: {
            color: color,
            opacity: 0.8,
            origin: 'start'
          },
          // Map values to rows: Aus = rowIdx - 1 (bottom of row), An = rowIdx (top of row)
          // We use step: 'end', so the value of a point is drawn UNTIL the next point.
          // To make it end at the last point, we don't add a final point in the backend.
          data: [...s.points]
            .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
            .map(p => [new Date(p.ts).getTime(), p.value ? rowIdx : rowIdx - 0.95])
        };
      })
    };
  };

  const enumOptions = (s: TimeSeries) => {
    const cats = Array.from(new Set((s.points.map(p => p.state).filter(Boolean) as string[]).concat((s as any).meta?.options || [])));
    return {
      tooltip: { 
        trigger: 'axis', 
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: { color: '#1e293b', fontSize: 12 }
      },
      grid: { left: '3%', right: '3%', bottom: 30, top: 10, containLabel: true },
      xAxis: { type: 'time', boundaryGap: false, axisLabel: { color: '#94a3b8', fontSize: 10 } },
      yAxis: { type: 'category', data: cats, axisLabel: { color: '#94a3b8', fontSize: 10 } },
      series: [
        {
          id: s.entity_id,
          name: s.friendly_name,
          type: 'line',
          step: 'end',
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 2.5, color: getSeriesColor(0) },
          itemStyle: { color: getSeriesColor(0) },
          areaStyle: { color: getSeriesColor(0), opacity: 0.05 },
          data: [...s.points]
            .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
            .map(p => [new Date(p.ts).getTime(), p.state || ''])
        }
      ]
    };
  };

  const stringOptions = (s: TimeSeries) => {
    const cats = Array.from(new Set(s.points.map(p => p.state).filter(Boolean) as string[]));
    return {
      tooltip: { 
        trigger: 'axis', 
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: { color: '#1e293b', fontSize: 12 }
      },
      grid: { left: '3%', right: '3%', bottom: 30, top: 10, containLabel: true },
      xAxis: { type: 'time', boundaryGap: false, axisLabel: { color: '#94a3b8', fontSize: 10 } },
      yAxis: { type: 'category', data: cats, axisLabel: { color: '#94a3b8', fontSize: 10 } },
      series: [
        {
          id: s.entity_id,
          name: s.friendly_name,
          type: 'line',
          step: 'end',
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 2.5, color: getSeriesColor(2) },
          itemStyle: { color: getSeriesColor(2) },
          areaStyle: { color: getSeriesColor(2), opacity: 0.05 },
          data: [...s.points]
            .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
            .map(p => [new Date(p.ts).getTime(), p.state || ''])
        }
      ]
    };
  };

  const onChartReadySetGroup = (instance: any) => {
    if (!instance) return;
    instance.group = groupId;
    // Verzögerte Verbindung, um sicherzustellen, dass alle Instanzen bereit sind
    setTimeout(() => {
      echarts.connect(groupId);
    }, 100);
  };

  // Modal TimeRange change handler
  const handleRangeChange = (rangeId: string) => {
    setModalTimeRange(rangeId);
  };

  // Keyboard accessibility: Close modal on Esc key
  useEffect(() => {
    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedEntityForModal(null);
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => {
      window.removeEventListener('keydown', handleEsc);
    };
  }, []);

  if (isDeviceLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <p className="text-slate-500 animate-pulse">Lade Gerätedaten...</p>
      </div>
    );
  }

  if (deviceError || !device) {
    return (
      <div className="bg-red-50 text-red-600 p-8 rounded-xl border border-red-100 flex flex-col items-center text-center">
        <XCircle className="w-12 h-12 mb-4 opacity-50" />
        <h3 className="font-bold text-lg mb-2">Gerät nicht gefunden</h3>
        <p className="mb-6">Das angeforderte Gerät existiert nicht oder Sie haben keine Berechtigung.</p>
        <Link to="/devices" className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition">
          Zurück zur Übersicht
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumbs & Header */}
      <div className="space-y-4">
        <nav className="flex items-center gap-2 text-sm text-slate-500">
          <Link to="/devices" className="hover:text-blue-600 transition">Geräte</Link>
          <ChevronRight className="w-4 h-4" />
          <span className="text-slate-900 font-medium">{device.display_name}</span>
        </nav>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <div className="flex items-center gap-4">
            <div className="bg-blue-50 p-3 rounded-xl text-blue-600">
              <Database className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">{device.display_name}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-slate-500 text-sm font-mono">{device.slug}</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${device.is_online ? 'bg-green-500 animate-pulse' : 'bg-slate-300'}`}></div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    device.is_online ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                  }`}>
                    {device.is_online ? 'Online' : 'Offline'}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/devices" className="px-4 py-2 text-slate-600 hover:bg-slate-50 border border-slate-200 rounded-lg transition text-sm font-medium flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              <span>Zurück</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 overflow-x-auto no-scrollbar bg-white rounded-t-xl px-2">
        {[
          { id: 'overview', label: 'Übersicht', icon: Activity },
          { id: 'dashboard', label: 'Dashboard', icon: Layout },
          { id: 'entities', label: 'Alle Entitäten', icon: List },
          { id: 'charts', label: 'Verläufe', icon: BarChart3 },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-6 py-4 font-medium flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
              activeTab === tab.id 
                ? 'border-blue-600 text-blue-600' 
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="min-h-[400px]">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2 space-y-6">
                {/* Stammdaten */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                  <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                    <Info className="w-4 h-4 text-blue-600" />
                    <h3 className="font-bold text-slate-900">Geräte-Informationen</h3>
                  </div>
                  <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-y-6 gap-x-4">
                    <div>
                      <p className="text-slate-500 text-xs uppercase tracking-wider font-semibold mb-1">Kunde / Mandant</p>
                      <p className="text-slate-900 font-medium">{tenant?.name || (device.tenant_id ? 'Lädt...' : 'Nicht zugeordnet')}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs uppercase tracking-wider font-semibold mb-1">Typ</p>
                      <p className="text-slate-900 font-medium capitalize">{device.source_type.replace('_', ' ')}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs uppercase tracking-wider font-semibold mb-1">Influx-Datenbank</p>
                      <p className="text-slate-900 font-mono text-sm">{device.influx_database_name}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs uppercase tracking-wider font-semibold mb-1">Erstellt am</p>
                      <p className="text-slate-900 font-medium">{new Date(device.created_at).toLocaleDateString('de-DE')}</p>
                    </div>
                  </div>
                </div>

                {/* Zusammenfassung Zustände */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                  <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-blue-600" />
                    <h3 className="font-bold text-slate-900">Aktuelle Zustände</h3>
                  </div>
                  <div className="p-6">
                    {isEntitiesLoading ? (
                      <div className="animate-pulse space-y-3">
                        <div className="h-4 bg-slate-100 rounded w-3/4"></div>
                        <div className="h-4 bg-slate-100 rounded w-1/2"></div>
                      </div>
                    ) : entities && entities.length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {entities.filter(e => e.domain === 'sensor' || e.domain === 'binary_sensor').slice(0, 8).map(entity => (
                          <div key={entity.entity_id} className="flex flex-col p-3 bg-slate-50 rounded-lg border border-slate-100 hover:border-blue-200 transition-colors group">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tighter truncate" title={entity.entity_id}>
                                {entity.friendly_name}
                              </span>
                              {entity.last_seen && (
                                <span className="text-[9px] text-slate-300 whitespace-nowrap">
                                  {new Date(entity.last_seen).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                                </span>
                              )}
                            </div>
                            <div className="mt-1 flex items-baseline gap-1">
                              <span className={`text-sm font-bold ${entity.last_value !== undefined ? 'text-blue-600' : 'text-slate-300 italic'}`}>
                                {entity.last_value !== undefined 
                                  ? (typeof entity.last_value === 'number' ? entity.last_value.toLocaleString('de-DE', { maximumFractionDigits: 1 }) : entity.last_value)
                                  : 'Keine Daten'}
                              </span>
                              {entity.last_value !== undefined && entity.unit_of_measurement && (
                                <span className="text-[10px] text-slate-400 font-medium">{entity.unit_of_measurement}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-slate-400 italic text-sm text-center py-4">
                        Keine Entitäten für dieses Gerät gefunden.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                {/* Status Cards */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                   <h3 className="text-slate-500 text-xs uppercase tracking-wider font-semibold mb-3">System-Status</h3>
                   <div className="flex items-center justify-between">
                     <div className="flex items-center gap-3">
                       <div className={`w-3 h-3 rounded-full ${device.is_online ? 'bg-green-500 animate-pulse' : 'bg-slate-300'} shadow-[0_0_8px_rgba(34,197,94,0.4)]`}></div>
                       <span className="font-bold text-slate-900">{device.is_online ? 'Verbunden' : 'Keine Verbindung'}</span>
                     </div>
                     <span className="text-xs text-slate-400">Live</span>
                   </div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                   <h3 className="text-slate-500 text-xs uppercase tracking-wider font-semibold mb-3">Datenpunkte</h3>
                   <div className="flex items-end gap-2">
                     <p className="text-3xl font-bold text-slate-900">{entities?.length || 0}</p>
                     <p className="text-slate-400 text-sm mb-1">Entitäten</p>
                   </div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                   <h3 className="text-slate-500 text-xs uppercase tracking-wider font-semibold mb-3">Letzte Aktivität</h3>
                   <div className="flex items-center gap-3 text-slate-700">
                     <Clock className="w-5 h-5 text-blue-500" />
                     <div>
                       <p className="font-medium">
                         {device.last_seen ? (
                           new Date(device.last_seen).getTime() > Date.now() - 300000 
                             ? 'Gerade eben' 
                             : new Date(device.last_seen).toLocaleString('de-DE')
                         ) : 'Noch nie'}
                       </p>
                       <p className="text-xs text-slate-400">
                         {device.is_online ? 'Synchronisierung aktiv' : 'Wartet auf Daten...'}
                       </p>
                     </div>
                   </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'entities' && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="relative md:col-span-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 block">Suche</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Name oder ID..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 transition text-sm"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 block">Bereich (Domain)</label>
                  <select 
                    value={domainFilter}
                    onChange={(e) => setDomainFilter(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 transition text-sm"
                  >
                    <option value="all">Alle Bereiche</option>
                    {domains.map(d => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 block">Datentyp</label>
                  <select 
                    value={kindFilter}
                    onChange={(e) => setKindFilter(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 transition text-sm"
                  >
                    <option value="all">Alle Typen</option>
                    {dataKinds.map(k => (
                      <option key={k} value={k}>{translateDataKind(k)}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 block">Visualisierbar</label>
                  <select 
                    value={chartableFilter}
                    onChange={(e) => setChartableFilter(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 transition text-sm"
                  >
                    <option value="all">Alle anzeigen</option>
                    <option value="yes">Ja (Diagramm möglich)</option>
                    <option value="no">Nein</option>
                  </select>
                </div>
              </div>

              {(searchQuery || domainFilter !== 'all' || kindFilter !== 'all' || chartableFilter !== 'all') && (
                <div className="flex justify-end">
                  <button 
                    onClick={() => {
                      setSearchQuery('');
                      setDomainFilter('all');
                      setKindFilter('all');
                      setChartableFilter('all');
                    }}
                    className="text-xs text-blue-600 hover:underline font-medium"
                  >
                    Filter zurücksetzen
                  </button>
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              {isEntitiesLoading ? (
                <div className="p-12 text-center space-y-4">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="text-slate-500">Lade Entitäten-Liste...</p>
                </div>
              ) : (
                <div className="overflow-x-auto -mx-4 md:mx-0">
                  <div className="inline-block min-w-full align-middle px-4 md:px-0">
                    <table className="min-w-full text-left border-collapse table-auto">
                      <thead>
                        <tr className="bg-slate-50 text-slate-500 text-[10px] uppercase tracking-wider font-bold border-b border-slate-100">
                          <th className="px-6 py-4 min-w-[300px]">Name / ID</th>
                          <th className="px-6 py-4">Bereich</th>
                          <th className="px-6 py-4">Datentyp</th>
                          <th className="px-6 py-4 text-center whitespace-nowrap">Visualisierbar</th>
                          <th className="px-6 py-4 text-right">Aktion</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {filteredEntities?.map(entity => (
                          <tr 
                            key={entity.entity_id} 
                            className="hover:bg-blue-50/30 transition group cursor-pointer"
                            onClick={() => {
                              setSelectedEntityForModal(entity);
                              setModalTimeRange('12h');
                            }}
                          >
                            <td className="px-6 py-4">
                              <div className="font-bold text-slate-900 group-hover:text-blue-700 transition" title={entity.friendly_name}>{entity.friendly_name}</div>
                              <div className="text-[10px] text-slate-400 font-mono mt-0.5" title={entity.entity_id}>{entity.entity_id}</div>
                            </td>
                            <td className="px-6 py-4">
                              <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-tight">{entity.domain}</span>
                            </td>
                            <td className="px-6 py-4">
                               <div className="text-xs text-slate-600 font-medium">{translateDataKind(entity.data_kind)}</div>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex justify-center">
                                {entity.chartable ? (
                                  <div className="flex items-center gap-1.5 text-green-600 bg-green-50 px-2 py-1 rounded-full text-[10px] font-bold border border-green-100">
                                    <CheckCircle2 className="w-3 h-3" />
                                    <span>DIAGRAMM</span>
                                  </div>
                                ) : (
                                  <div className="flex items-center gap-1.5 text-slate-400 bg-slate-50 px-2 py-1 rounded-full text-[10px] font-bold border border-slate-100">
                                    <Info className="w-3 h-3" />
                                    <span>TEXT/STATUS</span>
                                  </div>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button 
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleDashboard(entity);
                                  }}
                                  className={`p-1.5 rounded-lg border transition ${
                                    dashboardItems.some(i => i.id === entity.entity_id)
                                      ? 'bg-amber-50 border-amber-200 text-amber-600 shadow-sm'
                                      : 'bg-white border-slate-200 text-slate-400 hover:border-amber-300 hover:text-amber-600'
                                  }`}
                                  title={dashboardItems.some(i => i.id === entity.entity_id) ? 'Vom Dashboard entfernen' : 'Zum Dashboard hinzufügen'}
                                >
                                  <Star className={`w-4 h-4 ${dashboardItems.some(i => i.id === entity.entity_id) ? 'fill-amber-500' : ''}`} />
                                </button>

                                {entity.chartable && (
                                  <button 
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      toggleEntity(entity.entity_id);
                                    }}
                                    className={`text-[10px] font-bold px-3 py-1.5 rounded-lg transition uppercase tracking-wider ${
                                      selectedEntities.includes(entity.entity_id)
                                        ? 'bg-blue-600 text-white shadow-sm shadow-blue-200'
                                        : 'bg-white border border-slate-200 text-slate-600 hover:border-blue-300 hover:text-blue-600'
                                    }`}
                                  >
                                    {selectedEntities.includes(entity.entity_id) ? 'Abwählen' : 'Vergleichen'}
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                        {filteredEntities?.length === 0 && (
                          <tr>
                            <td colSpan={5} className="px-6 py-16 text-center text-slate-400 bg-slate-50/30">
                              <div className="max-w-xs mx-auto">
                                <Search className="w-10 h-10 mx-auto mb-4 opacity-20" />
                                <h4 className="text-slate-900 font-bold mb-1">Keine Treffer</h4>
                                <p className="text-sm">Für die gewählten Filter wurden keine Entitäten gefunden. Versuchen Sie es mit anderen Kriterien.</p>
                              </div>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'charts' && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <div>
                  <h3 className="font-bold text-slate-900 text-lg">Vergleich & Verläufe</h3>
                  <p className="text-slate-500 text-sm">Visualisierung ausgewählter Messwerte</p>
                </div>
                
                <div className="flex flex-wrap items-center gap-2 p-1 bg-slate-100 rounded-xl w-fit">
                  {[
                    { id: '12h', label: '12 Std' },
                    { id: '24h', label: '24 Std' },
                    { id: 'today', label: 'Heute' },
                    { id: 'yesterday', label: 'Gestern' },
                    { id: 'this_week', label: 'Diese Woche' },
                    { id: 'this_month', label: 'Diesen Monat' }
                  ].map(range => (
                    <button
                      key={range.id}
                      onClick={() => setTimeRange(range.id)}
                      className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        timeRange === range.id 
                          ? 'bg-white text-blue-600 shadow-sm' 
                          : 'text-slate-500 hover:text-slate-800'
                      }`}
                    >
                      {range.label}
                    </button>
                  ))}
                </div>
              </div>

              {selectedEntities.length > 0 ? (
                <div className="space-y-6">
                  {/* Multi-Panel Darstellung analog Home Assistant */}
                  <div className="w-full space-y-8">
                    {isChartDataLoading ? (
                      <div className="h-[400px] w-full flex flex-col items-center justify-center gap-4 bg-slate-50/50 rounded-xl">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        <p className="text-slate-500 text-sm">Messdaten werden geladen...</p>
                      </div>
                    ) : chartData && chartData.series && chartData.series.length > 0 ? (
                      <>
                        {/* Numerische Gruppen je Einheit */}
                        {Array.from(buildPanels().numericGroups.entries()).map(([unit, list]: [string, TimeSeries[]], idx: number) => (
                          <div key={`num-${unit}-${idx}`} className="h-[350px] border-b border-slate-50 pb-6 last:border-0 last:pb-0">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Vergleich {unit !== '—' ? `(${unit})` : 'Numerisch'}</span>
                            </div>
                            <ReactECharts
                              option={numericOptions(list, unit === '—' ? '' : unit)}
                              style={{ height: '100%', width: '100%' }}
                              notMerge={true}
                              lazyUpdate={true}
                              onChartReady={onChartReadySetGroup}
                            />
                          </div>
                        ))}

                        {/* Binär gemeinsam */}
                        {buildPanels().binaries.length > 0 && (
                          <div 
                            className="border-b border-slate-50 pb-6 last:border-0 last:pb-0"
                            style={{ height: `${Math.max(150, buildPanels().binaries.length * 45 + 80)}px` }}
                          >
                            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Status-Verlauf (An/Aus)</div>
                            <ReactECharts
                              option={binaryOptions(buildPanels().binaries)}
                              style={{ height: '100%', width: '100%' }}
                              notMerge={true}
                              lazyUpdate={true}
                              onChartReady={onChartReadySetGroup}
                            />
                          </div>
                        )}

                        {/* Enum/String als Zustandsbänder, je Entität eigenes Panel */}
                        {buildPanels().enums.map((s: TimeSeries, i: number) => (
                          <div key={`enum-${s.entity_id}-${i}`} className="h-[180px] border-b border-slate-50 pb-6 last:border-0 last:pb-0">
                            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Zustand: {s.friendly_name}</div>
                            <ReactECharts
                              option={enumOptions(s)}
                              style={{ height: '100%', width: '100%' }}
                              notMerge={true}
                              lazyUpdate={true}
                              onChartReady={onChartReadySetGroup}
                            />
                          </div>
                        ))}
                        {buildPanels().strings.map((s: TimeSeries, i: number) => (
                          <div key={`str-${s.entity_id}-${i}`} className="h-[180px] border-b border-slate-50 pb-6 last:border-0 last:pb-0">
                            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Text: {s.friendly_name}</div>
                            <ReactECharts
                              option={stringOptions(s)}
                              style={{ height: '100%', width: '100%' }}
                              notMerge={true}
                              lazyUpdate={true}
                              onChartReady={onChartReadySetGroup}
                            />
                          </div>
                        ))}
                      </>
                    ) : (
                      <div className="h-[400px] flex flex-col items-center justify-center text-slate-400 bg-slate-50/50 rounded-xl border border-dashed border-slate-200">
                        <Database className="w-12 h-12 text-slate-200 mb-4" />
                        <h4 className="text-slate-900 font-bold mb-1">Keine Daten verfügbar</h4>
                        <p className="text-sm px-6 text-center max-w-sm">
                          Im gewählten Zeitraum wurden keine Messwerte für die ausgewählten Entitäten gefunden.
                        </p>
                      </div>
                    )}
                  </div>
                  
                  <div className="p-5 bg-slate-50 rounded-2xl border border-slate-100">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                      <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                        <List className="w-3.5 h-3.5" />
                        Ausgewählte Entitäten ({selectedEntities.length})
                      </h4>
                      <button 
                        onClick={() => setActiveTab('entities')}
                        className="text-[10px] bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition font-bold shadow-sm shadow-blue-100 flex items-center gap-1.5"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        ENTITÄTEN VERWALTEN
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {selectedEntities.map((id, index) => {
                        const ent = entities?.find(e => e.entity_id === id);
                        return (
                          <div key={id} className="group flex items-center gap-2 bg-white px-3 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 shadow-sm hover:border-blue-300 transition-all">
                            <span className="w-3 h-3 rounded-full shadow-inner" style={{ backgroundColor: getSeriesColor(index) }}></span>
                            <div className="flex flex-col">
                              <span>{ent?.friendly_name || id}</span>
                              <span className="text-[9px] text-slate-400 font-mono leading-none">{ent?.unit_of_measurement || ''}</span>
                            </div>
                            <button 
                              onClick={() => toggleEntity(id)} 
                              className="ml-1 text-slate-300 group-hover:text-red-500 transition-colors p-1 rounded-lg hover:bg-red-50"
                              title="Entfernen"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-[450px] flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-100 rounded-3xl bg-slate-50/30">
                  <div className="bg-white p-6 rounded-3xl shadow-sm mb-6 border border-slate-100">
                    <BarChart3 className="w-12 h-12 text-blue-500" />
                  </div>
                  <h4 className="text-slate-900 text-xl font-bold mb-2">Vergleichsansicht vorbereiten</h4>
                  <p className="max-w-xs text-center text-slate-500 text-sm px-6 mb-8">
                    Wählen Sie die Entitäten aus, deren Verläufe Sie vergleichen oder analysieren möchten.
                  </p>
                  <button 
                    onClick={() => setActiveTab('entities')} 
                    className="bg-blue-600 text-white px-8 py-3 rounded-2xl hover:bg-blue-700 transition font-bold shadow-lg shadow-blue-200 flex items-center gap-2 active:scale-95"
                  >
                    <Plus className="w-5 h-5" />
                    Entitäten auswählen
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-xl shadow-sm border border-slate-200">
              <div>
                <h3 className="font-bold text-slate-900 text-lg">Mein Dashboard</h3>
                <p className="text-slate-500 text-sm">Individuelle Übersicht für dieses Gerät</p>
              </div>
              <button 
                onClick={() => setActiveTab('entities')}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition text-sm font-bold flex items-center gap-2 self-start md:self-auto"
              >
                <Plus className="w-4 h-4" />
                WIDGET HINZUFÜGEN
              </button>
            </div>

            {dashboardItems.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {dashboardItems.map(item => {
                  const props = {
                    key: item.id,
                    deviceId: deviceId!,
                    entityId: item.id,
                    title: item.title,
                    onRemove: () => removeFromDashboard(item.id),
                    onClick: () => {
                      const ent = entities?.find(e => e.entity_id === item.id);
                      if (ent) setSelectedEntityForModal(ent);
                    }
                  };

                  if (item.type === 'status') return <StatusWidget {...props} />;
                  if (item.type === 'mini-chart') return <MiniChartWidget {...props} />;
                  return <ValueWidget {...props} />;
                })}
              </div>
            ) : (
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-12 text-center flex flex-col items-center justify-center min-h-[400px]">
                <div className="bg-slate-50 p-6 rounded-full mb-6">
                  <Layout className="w-12 h-12 text-slate-300" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-2">Ihr Dashboard ist leer</h3>
                <p className="text-slate-500 max-w-sm mx-auto mb-8">
                  Fügen Sie wichtige Entitäten über den Reiter "Alle Entitäten" hinzu, um sie hier auf einen Blick zu sehen.
                </p>
                <button 
                  onClick={() => setActiveTab('entities')}
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition font-bold"
                >
                  Jetzt Entitäten auswählen
                </button>
              </div>
            )}
          </div>
        )}

        {/* Detail Modal */}
        {selectedEntityForModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm transition-all">
            <div className="bg-white w-full max-w-4xl rounded-2xl shadow-2xl overflow-hidden border border-slate-200 animate-in fade-in zoom-in duration-200">
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Activity className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 leading-tight">{selectedEntityForModal.friendly_name}</h3>
                    <p className="text-[10px] text-slate-400 font-mono">{selectedEntityForModal.entity_id}</p>
                  </div>
                </div>
                <button 
                  onClick={() => setSelectedEntityForModal(null)}
                  className="p-2 hover:bg-slate-200 rounded-full transition-colors"
                >
                  <XCircle className="w-6 h-6 text-slate-400" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 space-y-6">
                {/* Time Range Selector */}
                <div className="flex flex-wrap items-center gap-2 p-1 bg-slate-100 rounded-xl w-fit">
                  {[
                    { id: '12h', label: '12 Std' },
                    { id: 'today', label: 'Heute' },
                    { id: 'yesterday', label: 'Gestern' },
                    { id: 'this_week', label: 'Diese Woche' },
                    { id: 'this_month', label: 'Diesen Monat' }
                  ].map(range => (
                    <button
                      key={range.id}
                      onClick={() => handleRangeChange(range.id)}
                      className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        modalTimeRange === range.id 
                          ? 'bg-white text-blue-600 shadow-sm' 
                          : 'text-slate-500 hover:text-slate-800'
                      }`}
                    >
                      {range.label}
                    </button>
                  ))}
                </div>

                {/* Chart Area */}
                <div 
                  className="bg-slate-50 rounded-2xl border border-slate-100 p-4 relative overflow-hidden transition-all duration-300"
                  style={{ 
                    height: modalChartData?.series?.[0]?.data_kind === 'binary' 
                      ? '200px' 
                      : '350px' 
                  }}
                >
                  {isModalChartLoading ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/50 backdrop-blur-[2px] z-10">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                      <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Lade Daten...</p>
                    </div>
                  ) : null}
                  
                  {modalChartData?.series && modalChartData.series[0]?.points.length > 0 ? (
                    <ReactECharts
                      option={getModalChartOptions()}
                      style={{ height: '100%', width: '100%' }}
                      notMerge={true}
                    />
                  ) : !isModalChartLoading ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-3">
                      <Database className="w-10 h-10 opacity-20" />
                      <div className="text-center">
                        <p className="text-sm font-bold text-slate-600">Keine Daten für diesen Zeitraum vorhanden</p>
                        {modalChartData?.series && (modalChartData.series[0].meta as any)?.last_seen && (
                          <p className="text-xs text-amber-600 font-medium mt-1">
                            Letzter Datenpunkt gefunden am: {new Date((modalChartData.series[0].meta as any).last_seen).toLocaleString('de-DE')}
                          </p>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-400 max-w-[200px] text-center italic">
                        Versuchen Sie einen größeren Zeitraum (z.B. "Diesen Monat") zu wählen.
                      </p>
                    </div>
                  ) : null}
                </div>

                {/* Info Footer */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Bereich</p>
                    <p className="text-sm font-bold text-slate-700">{selectedEntityForModal.domain}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Datentyp</p>
                    <p className="text-sm font-bold text-slate-700">{translateDataKind(selectedEntityForModal.data_kind)}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Einheit</p>
                    <p className="text-sm font-bold text-slate-700">{selectedEntityForModal.unit_of_measurement || '—'}</p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                    <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Status</p>
                    <div className="flex items-center gap-1.5">
                      <div className={`w-2 h-2 rounded-full ${device.is_online ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`}></div>
                      <p className="text-sm font-bold text-slate-700">{device.is_online ? 'Verbunden' : 'Wartet auf Daten'}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DeviceDetailPage;
