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
import DeviceChatPanel from './components/DeviceChatPanel';

const DeviceDetailPage: React.FC = () => {
  const { deviceId } = useParams<{ deviceId: string }>();
  const [activeTab, setActiveTab] = useState<'overview' | 'entities' | 'charts' | 'dashboard' | 'chat'>('overview');
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

  const translateDomain = (domain: string) => {
    const translations: Record<string, string> = {
      sensor: 'Sensor',
      binary_sensor: 'Binärsensor',
      switch: 'Schalter',
      climate: 'Klima',
      number: 'Zahl',
      select: 'Auswahl',
      lock: 'Schloss',
      input_boolean: 'Boolescher Schalter',
      device_tracker: 'Gerätetracker',
      automation: 'Automatisierung',
      update: 'Update',
    };
    return translations[domain] || domain;
  };

  const filteredEntities = entities?.filter(e => {
    const matchesSearch = ((e.friendly_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.entity_id.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesDomain = domainFilter === 'all' || e.domain === domainFilter;
    const matchesKind = kindFilter === 'all' || e.data_kind === kindFilter;
    const matchesChartable = chartableFilter === 'all' || 
      (chartableFilter === 'yes' && e.chartable) || 
      (chartableFilter === 'no' && !e.chartable);
    
    return matchesSearch && matchesDomain && matchesKind && matchesChartable;
  });

  const toggleEntity = (id: string) => {
    setSelectedEntities(prev => 
      prev.includes(id) ? prev.filter(e => e !== id) : [...prev, id]
    );
  };

  const isBinaryLikeEntity = (entity: Entity) => {
    if (entity.data_kind === 'binary') {
      return true;
    }

    // Generic fallback for two-state timelines represented as enum/string
    if (entity.render_mode === 'state_timeline' && Array.isArray(entity.options)) {
      const distinctOptions = new Set(entity.options.map((option) => option?.trim()).filter(Boolean));
      return distinctOptions.size > 0 && distinctOptions.size <= 2;
    }

    return false;
  };

  const toggleDashboard = async (entity: Entity) => {
    if (!deviceId) return;
    
    let type: 'value' | 'status' | 'mini-chart' = 'value';
    if (isBinaryLikeEntity(entity)) type = 'status';
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

  const getSeriesColor = (index: number) => {
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];
    return colors[index % colors.length];
  };

  const getSeriesUnit = (series: TimeSeries, fallback = '') => {
    return series.unit_of_measurement || series.meta?.unit_of_measurement || fallback;
  };

  const getRangeBounds = (rangeResolved?: DeviceDataResponse['range_resolved']) => {
    return {
      minTime: rangeResolved?.from ? new Date(rangeResolved.from).getTime() : undefined,
      maxTime: rangeResolved?.to ? new Date(rangeResolved.to).getTime() : undefined,
    };
  };

  const formatTimeAxisLabel = (value: number, rangeKey: string) => {
    const date = new Date(value);
    const isShortRange = rangeKey === '12h' || rangeKey === 'today' || rangeKey === '24h';

    if (isShortRange) {
      return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    }

    if (date.getHours() === 0 && date.getMinutes() === 0) {
      return date.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
    }

    return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  };

  const buildTimeAxis = (rangeKey: string, rangeResolved?: DeviceDataResponse['range_resolved']) => {
    const { minTime, maxTime } = getRangeBounds(rangeResolved);

    return {
      type: 'time' as const,
      boundaryGap: false,
      min: minTime,
      max: maxTime,
      axisLabel: {
        color: '#94a3b8',
        fontSize: 10,
        hideOverlap: true,
        formatter: (value: number) => formatTimeAxisLabel(value, rangeKey),
      },
      axisLine: { show: false },
      splitLine: { show: false },
    };
  };

  const isActualPoint = (point: TimeSeries['points'][number]) => point.is_actual !== false;

  const getNumericPoints = (series: TimeSeries, includeSynthetic = false) => {
    return [...series.points]
      .filter(point => (includeSynthetic || isActualPoint(point)) && point.value !== null && point.value !== undefined)
      .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  };

  const hasRenderableSeries = (series: TimeSeries) => {
    if (series.render_mode === 'state_timeline') {
      return series.points.length > 0;
    }

    const numericPoints = getNumericPoints(series, series.render_mode === 'history_counter');
    return numericPoints.length > 0;
  };

  const isInstantLikeNumericSeries = (series: TimeSeries) => {
    if (series.render_mode === 'history_counter') {
      return false;
    }

    const deviceClass = (series.device_class || series.meta?.device_class || '').trim().toLowerCase();
    const unit = (series.unit_of_measurement || series.meta?.unit_of_measurement || '').trim().toLowerCase();
    const stateClass = (series.state_class || series.meta?.state_class || '').trim().toLowerCase();

    const instantDeviceClasses = new Set([
      'apparent_power',
      'current',
      'current_phase',
      'frequency',
      'power',
      'power_factor',
      'reactive_power',
      'signal_strength',
      'speed',
      'voltage',
      'volume_flow_rate',
      'wind_speed',
    ]);

    const statefulDeviceClasses = new Set([
      'aqi',
      'atmospheric_pressure',
      'battery',
      'carbon_dioxide',
      'carbon_monoxide',
      'distance',
      'duration',
      'energy',
      'energy_storage',
      'gas',
      'humidity',
      'illuminance',
      'irradiance',
      'moisture',
      'monetary',
      'nitrogen_dioxide',
      'nitrogen_monoxide',
      'nitrous_oxide',
      'ozone',
      'pm1',
      'pm10',
      'pm25',
      'precipitation',
      'precipitation_intensity',
      'pressure',
      'temperature',
      'volatile_organic_compounds',
      'volume',
      'volume_storage',
      'water',
      'weight',
    ]);

    const instantUnits = new Set(['a', 'hz', 'kw', 'l/h', 'm3/h', 'ma', 'mw', 'rpm', 'v', 'va', 'var', 'w']);
    const statefulUnits = new Set(['%', '°c', 'bar', 'c', 'kwh', 'l', 'm3', 'psi', 'wh']);

    if (instantDeviceClasses.has(deviceClass)) {
      return true;
    }

    if (statefulDeviceClasses.has(deviceClass)) {
      return false;
    }

    if (stateClass === 'measurement') {
      if (instantUnits.has(unit)) {
        return true;
      }

      if (statefulUnits.has(unit)) {
        return false;
      }

      return true;
    }

    if (series.value_semantics === 'instant') {
      return true;
    }

    if (series.value_semantics === 'stateful') {
      return false;
    }

    return false;
  };

  const isHeldValueSeries = (series: TimeSeries) => {
    return series.render_mode === 'history_counter' || isInstantLikeNumericSeries(series);
  };

  const buildNumericSeriesData = (
    series: TimeSeries,
  ) => {
    const numericPoints = getNumericPoints(series, true);
    const seriesData: Array<[number, number | null]> = [];

    numericPoints.forEach((point, index) => {
      const pointTime = new Date(point.ts).getTime();
      const pointValue = point.value ?? null;

      if (index === 0) {
        seriesData.push([pointTime, pointValue]);
        return;
      }

      const previousPoint = numericPoints[index - 1];
      const previousValue = previousPoint.value ?? null;

      if (isHeldValueSeries(series)) {
        seriesData.push([pointTime, previousValue]);
        seriesData.push([pointTime, pointValue]);
        return;
      }

      seriesData.push([pointTime, pointValue]);
    });

    return seriesData;
  };

  const buildNumericGapData = (
    series: TimeSeries,
    rangeResolved?: DeviceDataResponse['range_resolved'],
  ) => {
    const numericPoints = getNumericPoints(series, true);
    const { minTime, maxTime } = getRangeBounds(rangeResolved);
    const gapSegments: Array<[number, number]> = [];
    const gapData: Array<[number, number | null]> = [];

    const addGapSegment = (start: number, end: number) => {
      if (!(end > start)) return;
      gapSegments.push([start, end]);
      if (gapData.length > 0) {
        gapData.push([start, null]);
      }
      gapData.push([start, 0], [end, 0], [end, null]);
    };

    if (numericPoints.length === 0) {
      if (minTime !== undefined && maxTime !== undefined && maxTime > minTime) {
        addGapSegment(minTime, maxTime);
      }
      return { gapData, gapSegments };
    }

    const firstTime = new Date(numericPoints[0].ts).getTime();
    const lastTime = new Date(numericPoints[numericPoints.length - 1].ts).getTime();

    if (minTime !== undefined && firstTime > minTime) {
      addGapSegment(minTime, firstTime);
    }

    if (maxTime !== undefined && lastTime < maxTime) {
      addGapSegment(lastTime, maxTime);
    }

    return { gapData, gapSegments };
  };

  const isAxisInGap = (axisTime: number, gapSegments: Array<[number, number]>) => {
    return gapSegments.some(([start, end]) => axisTime >= start && axisTime <= end);
  };

  const getNumericValueAtAxis = (
    series: TimeSeries,
    axisTime: number,
    gapSegments: Array<[number, number]>,
  ) => {
    const numericPoints = getNumericPoints(series, true);

    if (numericPoints.length === 0 || isAxisInGap(axisTime, gapSegments)) {
      return null;
    }

    const firstTime = new Date(numericPoints[0].ts).getTime();
    const lastTime = new Date(numericPoints[numericPoints.length - 1].ts).getTime();

    if (axisTime < firstTime || axisTime > lastTime) {
      return null;
    }

    for (let index = 0; index < numericPoints.length; index += 1) {
      const point = numericPoints[index];
      const pointTime = new Date(point.ts).getTime();

      if (pointTime === axisTime) {
        return point.value ?? null;
      }

      const nextPoint = numericPoints[index + 1];
      if (!nextPoint) {
        continue;
      }

      const nextTime = new Date(nextPoint.ts).getTime();
      if (axisTime > pointTime && axisTime < nextTime) {
        if (isHeldValueSeries(series)) {
          return point.value ?? null;
        }

        const currentValue = point.value;
        const nextValue = nextPoint.value;
        if (currentValue === null || currentValue === undefined || nextValue === null || nextValue === undefined) {
          return null;
        }

        const ratio = (axisTime - pointTime) / (nextTime - pointTime);
        return currentValue + (nextValue - currentValue) * ratio;
      }
    }

    return numericPoints[numericPoints.length - 1]?.value ?? null;
  };

  const buildPanels = (seriesList: TimeSeries[]) => {
    const numericGroups = new Map<string, TimeSeries[]>();
    const binaryStates: TimeSeries[] = [];
    const categoricalStates: TimeSeries[] = [];

    const normalizeUnit = (unit: string) => {
      if (!unit) return '—';
      const normalized = unit.trim();
      const upper = normalized.toUpperCase();
      if (upper === '°C' || upper === 'C' || upper === 'GRAD' || upper === 'CELSIUS') return '°C';
      if (upper === '%' || upper === 'PROZENT') return '%';
      if (upper === 'BAR') return 'bar';
      return normalized;
    };

    seriesList
      .filter(series => series && series.entity_id)
      .forEach((series) => {
        if (series.render_mode === 'history_counter' || series.render_mode === 'history_line') {
          const unitKey = normalizeUnit(getSeriesUnit(series));
          if (!numericGroups.has(unitKey)) {
            numericGroups.set(unitKey, []);
          }
          numericGroups.get(unitKey)!.push(series);
          return;
        }

        if (series.render_mode === 'state_timeline') {
          if (series.data_kind === 'binary') {
            binaryStates.push(series);
          } else {
            categoricalStates.push(series);
          }
        }
      });

    return { numericGroups, binaryStates, categoricalStates };
  };

  const chartPanels = buildPanels(chartData?.series ?? []);
  const hasRenderedCharts = chartPanels.numericGroups.size > 0 || chartPanels.binaryStates.length > 0 || chartPanels.categoricalStates.length > 0;

  const groupId = deviceId ? `device-${deviceId}-compare` : 'compare-group';

  const numericOptions = (
    seriesList: TimeSeries[],
    unitLabel: string,
    rangeKey: string,
    rangeResolved?: DeviceDataResponse['range_resolved']
  ) => {
    const preparedSeries = seriesList.map((series, index) => {
      const color = getSeriesColor(index);
      const seriesData = buildNumericSeriesData(series);
      const { gapData, gapSegments } = buildNumericGapData(series, rangeResolved);

      return {
        series,
        color,
        seriesData,
        gapData,
        gapSegments,
      };
    });

    return {
      tooltip: { 
        trigger: 'axis', 
        confine: true,
        axisPointer: { 
          type: 'line',
          lineStyle: { color: '#cbd5e1', width: 1 },
          z: 10,
        },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: '#1e293b', fontSize: 12 },
        extraCssText: 'shadow-md rounded-lg border border-slate-200',
        formatter: (params: any) => {
          const axisParams = Array.isArray(params) ? params.filter((entry: any) => entry.componentType === 'series') : [];
          if (axisParams.length === 0) return '';

          let res = `<div class="font-bold text-slate-500 text-[10px] mb-1.5 uppercase tracking-wider">${axisParams[0].axisValueLabel}</div>`;
          const axisTime = typeof axisParams[0].axisValue === 'number'
            ? axisParams[0].axisValue
            : new Date(axisParams[0].axisValue).getTime();

          preparedSeries.forEach((entry) => {
            const unit = getSeriesUnit(entry.series, unitLabel);
            const rawValue = getNumericValueAtAxis(entry.series, axisTime, entry.gapSegments);
            const formattedValue = typeof rawValue === 'number'
              ? `${rawValue.toLocaleString('de-DE', { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ''}`
              : 'Keine Daten';
            res += `<div class="flex items-center justify-between gap-6 py-0.5">
                      <div class="flex items-center gap-2">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background-color:${entry.color};"></span>
                        <span class="text-slate-600 font-medium">${entry.series.friendly_name}</span>
                      </div>
                      <span class="font-bold text-slate-900">${formattedValue}</span>
                    </div>`;
          });

          return res;
        }
      },
      grid: { left: '3%', right: '3%', bottom: 30, top: 40, containLabel: true },
      legend: {
        show: seriesList.length > 1,
        top: 0,
        icon: 'roundRect',
        textStyle: { color: '#64748b', fontSize: 11 },
        itemWidth: 12,
        itemHeight: 4
      },
      xAxis: buildTimeAxis(rangeKey, rangeResolved),
      yAxis: { 
        type: 'value', 
        scale: true,
        name: unitLabel || undefined, 
        nameTextStyle: { color: '#94a3b8', fontSize: 10 },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f1f5f9' } }
      },
      series: preparedSeries.flatMap((entry) => {
        return [
          {
            id: `${entry.series.entity_id}__gap`,
            name: entry.series.friendly_name,
            type: 'line',
            tooltip: { show: false },
            silent: true,
            showSymbol: false,
            connectNulls: false,
            z: 1,
            lineStyle: {
              width: 1.5,
              color: entry.color,
              opacity: 0.45,
              type: 'dashed',
            },
            data: entry.gapData,
          },
          {
            id: entry.series.entity_id,
            name: entry.series.friendly_name,
            type: 'line',
            showSymbol: false, 
            step: false,
            smooth: false, 
            connectNulls: false,
            z: 3,
            lineStyle: { 
              width: entry.series.render_mode === 'history_counter' ? 2 : 1.5,
              color: entry.color,
              opacity: 1
            },
            itemStyle: { color: entry.color },
            data: entry.seriesData
          }
        ];
      })
    };
  };

  // ──────────────────────────────────────────────────────────────
  // HA-style State-Timeline: coloured segments with inline labels
  // ──────────────────────────────────────────────────────────────

  /** Stable colour palette per unique state label (like HA's default) */
  const STATE_PALETTE: Record<string, string> = {
    // binary / on-off
    'an': '#22c55e',
    'on': '#22c55e',
    'active': '#22c55e',
    'heating': '#ef4444',
    'heizen': '#ef4444',
    'aus': '#e2e8f0',
    'off': '#e2e8f0',
    'inactive': '#e2e8f0',
    'idle': '#94a3b8',
    'standby': '#94a3b8',
    'cooling': '#3b82f6',
    'kühlen': '#3b82f6',
    'defrost': '#8b5cf6',
    'defrost abtauen': '#8b5cf6',
    'error': '#f97316',
    'fehler': '#f97316',
  };

  const STATE_FALLBACK_COLORS = [
    '#6366f1', '#0ea5e9', '#f59e0b', '#10b981',
    '#ec4899', '#14b8a6', '#f97316', '#a78bfa',
  ];

  const stateColorCache = new Map<string, string>();

  const getStateColor = (label: string): string => {
    const key = label.toLowerCase().trim();
    if (STATE_PALETTE[key]) return STATE_PALETTE[key];
    if (stateColorCache.has(key)) return stateColorCache.get(key)!;
    const color = STATE_FALLBACK_COLORS[stateColorCache.size % STATE_FALLBACK_COLORS.length];
    stateColorCache.set(key, color);
    return color;
  };

  const getStateTextColor = (bg: string): string => {
    // simple luminance check: use dark text on light backgrounds
    const hex = bg.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.60 ? '#374151' : '#ffffff';
  };

  /**
   * Converts a sorted point list into closed segments:
   * [{start, end, label}]
   * The last segment is extended to `rangeEnd` (now).
   */
  const buildStateSegments = (
    series: TimeSeries,
    rangeResolved?: DeviceDataResponse['range_resolved'],
  ) => {
    const { maxTime } = getRangeBounds(rangeResolved);
    const rangeEnd = maxTime ?? Date.now();

    const sorted = [...series.points]
      .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

    if (sorted.length === 0) return [] as Array<{ start: number; end: number; label: string }>;

    const segments: Array<{ start: number; end: number; label: string }> = [];

    for (let i = 0; i < sorted.length; i++) {
      const pt = sorted[i];
      const start = new Date(pt.ts).getTime();
      const end = i < sorted.length - 1
        ? new Date(sorted[i + 1].ts).getTime()
        : rangeEnd;

      const label = series.data_kind === 'binary'
        ? (pt.value ? 'an' : 'aus')
        : (pt.state || String(pt.value ?? ''));

      if (end > start) {
        segments.push({ start, end, label });
      }
    }

    return segments;
  };

  /**
   * One HA-style state-bar chart for one or many series.
   * Each series gets its own labelled row.
   */
  const stateBarOptions = (
    seriesList: TimeSeries[],
    rangeKey: string,
    rangeResolved?: DeviceDataResponse['range_resolved'],
  ) => {
    const { minTime, maxTime } = getRangeBounds(rangeResolved);
    const BAR_HEIGHT = 28;   // px per row
    const ROW_GAP = 8;       // px between rows
    const LABEL_PX = 140;    // left label column width

    const rows = seriesList.map((series) => ({
      series,
      segments: buildStateSegments(series, rangeResolved),
    }));

    const totalRows = rows.length;
    const chartHeight = totalRows * (BAR_HEIGHT + ROW_GAP) + 24; // +24 for bottom axis

    // custom render function passed to ECharts
    const renderItem = (_params: any, api: any) => {
      const rowIndex: number = api.value(0);
      const segStart: number = api.value(1);
      const segEnd: number = api.value(2);
      const label: string = api.value(3);

      const startCoord = api.coord([segStart, rowIndex]);
      const endCoord = api.coord([segEnd, rowIndex]);

      const x = startCoord[0];
      const y = startCoord[1] - BAR_HEIGHT / 2;
      const width = Math.max(endCoord[0] - startCoord[0], 1);
      const height = BAR_HEIGHT;

      const bg = getStateColor(label);
      const fg = getStateTextColor(bg);

      // only show label if segment is wide enough (≥30px)
      const showLabel = width >= 30;

      return {
        type: 'group',
        children: [
          {
            type: 'rect',
            shape: { x, y, width, height, r: 3 },
            style: { fill: bg, stroke: 'none' },
            z2: 1,
          },
          ...(showLabel ? [{
            type: 'text',
            style: {
              text: label,
              x: x + width / 2,
              y: y + height / 2,
              textAlign: 'center',
              textVerticalAlign: 'middle',
              fill: fg,
              fontSize: 11,
              fontWeight: '600',
              fontFamily: 'inherit',
              overflow: 'truncate',
              width: width - 6,
            },
            z2: 2,
          }] : []),
        ],
      };
    };

    // flatten all rows into one data array: [rowIndex, start, end, label]
    const data: [number, number, number, string][] = [];
    rows.forEach((row, rowIdx) => {
      row.segments.forEach((seg) => {
        data.push([rowIdx, seg.start, seg.end, seg.label]);
      });
    });

    const yAxisLabels = rows.map((r) => r.series.friendly_name);

    return {
      _stateBarChartHeight: chartHeight,
      tooltip: {
        trigger: 'item',
        confine: true,
        backgroundColor: 'rgba(255,255,255,0.98)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: { color: '#1e293b', fontSize: 12 },
        extraCssText: 'box-shadow:0 4px 6px -1px rgb(0 0 0/0.1);border-radius:8px;padding:10px;',
        formatter: (params: any) => {
          if (!params?.data) return '';
          const [rowIdx, segStart, segEnd, label] = params.data as [number, number, number, string];
          const name = yAxisLabels[rowIdx] ?? '';
          const dur = segEnd - segStart;
          const mins = Math.round(dur / 60000);
          const durStr = mins >= 60
            ? `${Math.floor(mins / 60)}h ${mins % 60}min`
            : `${mins} min`;
          const bg = getStateColor(label);
          return `<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px">${name}</div>
                  <div style="display:flex;align-items:center;gap:8px">
                    <span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${bg};"></span>
                    <span style="font-weight:700;font-size:13px;color:#0f172a">${label}</span>
                  </div>
                  <div style="color:#94a3b8;font-size:11px;margin-top:4px">
                    ${new Date(segStart).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                    → ${new Date(segEnd).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                    · ${durStr}
                  </div>`;
        },
      },
      grid: {
        left: LABEL_PX,
        right: 12,
        top: 6,
        bottom: 28,
        containLabel: false,
      },
      xAxis: {
        type: 'time',
        min: minTime,
        max: maxTime,
        boundaryGap: false,
        splitLine: { show: true, lineStyle: { color: '#f1f5f9' } },
        axisLine: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          hideOverlap: true,
          formatter: (value: number) => formatTimeAxisLabel(value, rangeKey),
        },
      },
      yAxis: {
        type: 'value',
        min: -0.5,
        max: totalRows - 0.5,
        interval: 1,
        inverse: false,
        axisLabel: {
          show: true,
          color: '#374151',
          fontSize: 11,
          fontWeight: 600,
          width: LABEL_PX - 12,
          overflow: 'truncate',
          formatter: (value: number) => {
            const idx = Math.round(value);
            return yAxisLabels[idx] ?? '';
          },
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
      series: [
        {
          type: 'custom',
          renderItem,
          encode: { x: [1, 2], y: 0 },
          data,
          z: 2,
        },
      ],
    };
  };

  const binaryTimelineOptions = (
    seriesList: TimeSeries[],
    rangeKey: string,
    rangeResolved?: DeviceDataResponse['range_resolved'],
  ) => stateBarOptions(seriesList, rangeKey, rangeResolved);

  const categoricalTimelineOptions = (
    series: TimeSeries,
    rangeKey: string,
    rangeResolved?: DeviceDataResponse['range_resolved'],
  ) => stateBarOptions([series], rangeKey, rangeResolved);

  const stateTimelineOptions = (
    seriesList: TimeSeries[],
    rangeKey: string,
    rangeResolved?: DeviceDataResponse['range_resolved']
  ) => {
    if (seriesList.every(series => series.data_kind === 'binary')) {
      return binaryTimelineOptions(seriesList, rangeKey, rangeResolved);
    }
    return categoricalTimelineOptions(seriesList[0], rangeKey, rangeResolved);
  };

  const getModalChartOptions = () => {
    if (!modalChartData || !modalChartData.series || modalChartData.series.length === 0) return {};
    const series = modalChartData.series[0];

    if (series.render_mode === 'state_timeline') {
      return stateTimelineOptions([series], modalTimeRange, modalChartData.range_resolved);
    }

    return numericOptions([series], getSeriesUnit(series), modalTimeRange, modalChartData.range_resolved);
  };

  const hasRenderableModalSeries = () => {
    if (!modalChartData?.series?.[0]) {
      return false;
    }

    return hasRenderableSeries(modalChartData.series[0]);
  };

  const onChartReadySetGroup = (instance: any) => {
    if (!instance) return;
    instance.group = groupId;
    // Sofortige Verbindung versuchen
    echarts.connect(groupId);
    // Erneute Verbindung nach Verzögerung, falls DOM noch nicht stabil
    setTimeout(() => {
      echarts.connect(groupId);
    }, 500);
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
            <Link to={`/devices/${device.id}/chat`} className="px-4 py-2 text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg transition text-sm font-medium flex items-center gap-2">
              <Search className="w-4 h-4" />
              <span>KI-Chat</span>
            </Link>
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
          { id: 'charts', label: 'Vergleiche', icon: BarChart3 },
          { id: 'chat', label: 'KI-Chat', icon: Search },
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
                      <option key={d} value={d}>{translateDomain(d)}</option>
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
                              <div className="font-bold text-slate-900 group-hover:text-blue-700 transition" title={entity.friendly_name || entity.entity_id}>{entity.friendly_name || entity.entity_id}</div>
                              <div className="text-[10px] text-slate-400 font-mono mt-0.5" title={entity.entity_id}>{entity.entity_id}</div>
                            </td>
                            <td className="px-6 py-4">
                              <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-tight">{translateDomain(entity.domain)}</span>
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
                  <h3 className="font-bold text-slate-900 text-lg">Vergleiche</h3>
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
                    ) : chartData && chartData.series && hasRenderedCharts ? (
                      <>
                        {/* Numerische Gruppen je Einheit */}
                        {Array.from(chartPanels.numericGroups.entries()).map(([unit, list]: [string, TimeSeries[]], idx: number) => (
                          <div key={`num-${unit}-${idx}`} className="h-[350px] border-b border-slate-50 pb-6 last:border-0 last:pb-0">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Vergleich {unit !== '—' ? `(${unit})` : 'Numerisch'}</span>
                            </div>
                            <ReactECharts
                              option={numericOptions(list, unit === '—' ? '' : unit, timeRange, chartData.range_resolved)}
                              style={{ height: '100%', width: '100%' }}
                              notMerge={true}
                              lazyUpdate={true}
                              onChartReady={onChartReadySetGroup}
                            />
                          </div>
                        ))}

                        {/* Binär gemeinsam */}
                        {chartPanels.binaryStates.length > 0 && (() => {
                          const h = Math.max(72, chartPanels.binaryStates.length * 36 + 34);
                          return (
                            <div
                              className="border-b border-slate-50 pb-4 last:border-0 last:pb-0"
                              style={{ height: `${h + 22}px` }}
                            >
                              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Status-Verlauf (An/Aus)</div>
                              <ReactECharts
                                option={stateTimelineOptions(chartPanels.binaryStates, timeRange, chartData.range_resolved)}
                                style={{ height: `${h}px`, width: '100%' }}
                                notMerge={true}
                                lazyUpdate={true}
                                onChartReady={onChartReadySetGroup}
                              />
                            </div>
                          );
                        })()}

                        {/* Weitere State-Timelines, je Entität eigenes Panel */}
                        {chartPanels.categoricalStates.map((s: TimeSeries, i: number) => {
                          const h = 62; // 1 row = 28px bar + gaps + axis
                          return (
                            <div key={`state-${s.entity_id}-${i}`} className="border-b border-slate-50 pb-4 last:border-0 last:pb-0" style={{ height: `${h + 22}px` }}>
                              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Zustand: {s.friendly_name}</div>
                              <ReactECharts
                                option={stateTimelineOptions([s], timeRange, chartData.range_resolved)}
                                style={{ height: `${h}px`, width: '100%' }}
                                notMerge={true}
                                lazyUpdate={true}
                                onChartReady={onChartReadySetGroup}
                              />
                            </div>
                          );
                        })}
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
                    Wählen Sie die Entitäten aus, die Sie vergleichen oder analysieren möchten.
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
                  const ent = entities?.find(e => e.entity_id === item.id);
                  const effectiveType: 'value' | 'status' | 'mini-chart' = (() => {
                    if (!ent) return item.type;
                    if (isBinaryLikeEntity(ent)) return 'status';
                    if (ent.render_mode === 'state_timeline') return 'mini-chart';
                    if (ent.chartable) return 'mini-chart';
                    return 'value';
                  })();

                  const props = {
                    deviceId: deviceId!,
                    entityId: item.id,
                    title: item.title,
                    onRemove: () => removeFromDashboard(item.id),
                    onClick: () => {
                      if (ent) setSelectedEntityForModal(ent);
                    }
                  };

                  if (effectiveType === 'status') return <StatusWidget key={item.id} {...props} />;
                  if (effectiveType === 'mini-chart') return <MiniChartWidget key={item.id} {...props} />;
                  return <ValueWidget key={item.id} {...props} />;
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

        {activeTab === 'chat' && deviceId && (
          <DeviceChatPanel deviceId={deviceId} />
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
                {(() => {
                  const isStateBar = modalChartData?.series?.[0]?.render_mode === 'state_timeline';
                  // 1 row needs: top(6) + bar(28) + gap(8) + bottom(28) = 70px chart, +16px headroom
                  const chartH = isStateBar ? 86 : 350;
                  // container adds p-4 = 16px top + 16px bottom = 32px
                  const containerH = isStateBar ? chartH + 32 : chartH;
                  return (
                <div 
                  className="bg-slate-50 rounded-2xl border border-slate-100 p-4 relative overflow-hidden transition-all duration-300"
                  style={{ height: `${containerH}px` }}
                >
                  {isModalChartLoading ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/50 backdrop-blur-[2px] z-10">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                      <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Lade Daten...</p>
                    </div>
                  ) : null}
                  
                  {hasRenderableModalSeries() ? (
                    <ReactECharts
                      option={getModalChartOptions()}
                      style={{ height: `${chartH}px`, width: '100%' }}
                      notMerge={true}
                    />
                  ) : !isModalChartLoading ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-3">
                      <Database className="w-10 h-10 opacity-20" />
                      <div className="text-center">
                        <p className="text-sm font-bold text-slate-600">Keine Daten für diesen Zeitraum vorhanden</p>
                        {modalChartData?.series && modalChartData.series[0].meta?.last_seen && (
                          <p className="text-xs text-amber-600 font-medium mt-1">
                            Letzter Datenpunkt gefunden am: {new Date(modalChartData.series[0].meta.last_seen).toLocaleString('de-DE')}
                          </p>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-400 max-w-[200px] text-center italic">
                        Versuchen Sie einen größeren Zeitraum (z.B. "Diesen Monat") zu wählen.
                      </p>
                    </div>
                  ) : null}
                </div>
                  );
                })()}

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
