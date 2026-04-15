import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import { ReactECharts } from '../lib/echarts';
import type { DashboardDataPoint, DashboardEntityData, DeviceDashboardResponse } from '../types/api';
import { Trash2, Activity, AlertCircle } from 'lucide-react';

interface WidgetProps {
  deviceId: string;
  entityId: string;
  title: string;
  onRemove: () => void;
  onClick?: () => void;
}

const DASHBOARD_SPARKLINE_WINDOW_MS = 24 * 60 * 60 * 1000;

const getSparklineRange = () => {
  const maxTime = Date.now();
  return {
    minTime: maxTime - DASHBOARD_SPARKLINE_WINDOW_MS,
    maxTime,
  };
};

const getNumericSparklinePoints = (
  sparkline: DashboardDataPoint[],
  latestPoint?: DashboardDataPoint,
) => {
  const points = sparkline
    .filter((point) => typeof point.value === 'number')
    .map((point) => ({
      ts: new Date(point.ts).getTime(),
      value: point.value as number,
    }))
    .sort((a, b) => a.ts - b.ts);

  if (latestPoint && typeof latestPoint.value === 'number') {
    const latestTs = new Date(latestPoint.ts).getTime();
    const latestValue = latestPoint.value;
    const lastPoint = points[points.length - 1];

    if (!lastPoint || latestTs > lastPoint.ts) {
      points.push({ ts: latestTs, value: latestValue });
    }
  }

  return points;
};

const isInstantLikeSparklineSeries = (entityData?: DashboardEntityData) => {
  if (!entityData || entityData.render_mode === 'history_counter') {
    return false;
  }

  const deviceClass = (entityData.device_class || '').trim().toLowerCase();
  const unit = (entityData.unit_of_measurement || '').trim().toLowerCase();
  const stateClass = (entityData.state_class || '').trim().toLowerCase();

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

    return entityData.value_semantics === 'instant';
  }

  if (entityData.value_semantics === 'instant') {
    return true;
  }

  if (entityData.value_semantics === 'stateful') {
    return false;
  }

  return false;
};

const isHeldSparklineSeries = (entityData?: DashboardEntityData) => {
  if (!entityData) return false;
  return entityData.render_mode === 'history_counter' || isInstantLikeSparklineSeries(entityData);
};

const buildSparklineSeriesData = (entityData?: DashboardEntityData) => {
  const points = getNumericSparklinePoints(entityData?.sparkline || [], entityData?.latest_point);
  const heldSeries = isHeldSparklineSeries(entityData);
  const seriesData: Array<[number, number]> = [];

  points.forEach((point, index) => {
    if (index === 0) {
      seriesData.push([point.ts, point.value]);
      return;
    }

    const previousPoint = points[index - 1];

    if (heldSeries) {
      seriesData.push([point.ts, previousPoint.value]);
      seriesData.push([point.ts, point.value]);
      return;
    }

    seriesData.push([point.ts, point.value]);
  });

  return seriesData;
};

const STATE_PALETTE: Record<string, string> = {
  an: '#22c55e',
  on: '#22c55e',
  active: '#22c55e',
  heizen: '#ef4444',
  heating: '#ef4444',
  aus: '#e2e8f0',
  off: '#e2e8f0',
  inactive: '#e2e8f0',
  idle: '#94a3b8',
  standby: '#94a3b8',
  cooling: '#3b82f6',
  'k\u00fchlen': '#3b82f6',
  defrost: '#8b5cf6',
  error: '#f97316',
  fehler: '#f97316',
};

const STATE_FALLBACK_COLORS = ['#6366f1', '#0ea5e9', '#f59e0b', '#10b981', '#ec4899', '#14b8a6', '#f97316', '#a78bfa'];

const stateColorCache = new Map<string, string>();

const getStateColor = (label: string) => {
  const key = label.toLowerCase().trim();
  if (STATE_PALETTE[key]) return STATE_PALETTE[key];
  if (stateColorCache.has(key)) return stateColorCache.get(key)!;
  const color = STATE_FALLBACK_COLORS[stateColorCache.size % STATE_FALLBACK_COLORS.length];
  stateColorCache.set(key, color);
  return color;
};

const buildStateSparklineSegments = (
  entityData: DashboardEntityData | undefined,
  minTime: number,
  maxTime: number,
) => {
  if (!entityData) return [] as Array<{ start: number; end: number; label: string }>;

  const points = [...(entityData.sparkline || [])]
    .filter((point) => {
      if (entityData.data_kind === 'binary') {
        return point.value !== null && point.value !== undefined;
      }
      return typeof point.state === 'string' && point.state.length > 0;
    })
    .map((point) => ({
      ts: new Date(point.ts).getTime(),
      label: entityData.data_kind === 'binary'
        ? ((point.value === 1) ? 'an' : 'aus')
        : String(point.state || ''),
    }))
    .sort((a, b) => a.ts - b.ts);

  if (entityData.latest_point) {
    const latestTs = new Date(entityData.latest_point.ts).getTime();
    const latestLabel = entityData.data_kind === 'binary'
      ? ((entityData.latest_point.value === 1) ? 'an' : 'aus')
      : String(entityData.latest_point.state || '');
    const lastPoint = points[points.length - 1];

    if (latestLabel && (!lastPoint || latestTs > lastPoint.ts)) {
      points.push({ ts: latestTs, label: latestLabel });
    }
  }

  if (points.length === 0) return [];

  const segments: Array<{ start: number; end: number; label: string }> = [];

  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    const start = Math.max(current.ts, minTime);
    const end = Math.min(next ? next.ts : maxTime, maxTime);

    if (end > start) {
      segments.push({ start, end, label: current.label });
    }
  }

  return segments;
};

const buildStateSparklineOptions = (
  entityData: DashboardEntityData | undefined,
  minTime: number,
  maxTime: number,
) => {
  const segments = buildStateSparklineSegments(entityData, minTime, maxTime);
  const row = 0;
  const barHeight = 16;

  return {
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: {
      type: 'time',
      show: false,
      min: minTime,
      max: maxTime,
      boundaryGap: false,
    },
    yAxis: {
      type: 'value',
      show: false,
      min: -0.5,
      max: 0.5,
    },
    series: [
      {
        type: 'custom',
        renderItem: (_params: any, api: any) => {
          const start = api.value(1);
          const end = api.value(2);
          const label = api.value(3) as string;

          const startCoord = api.coord([start, row]);
          const endCoord = api.coord([end, row]);
          const width = Math.max(endCoord[0] - startCoord[0], 1);
          const x = startCoord[0];
          const y = startCoord[1] - barHeight / 2;

          return {
            type: 'rect',
            shape: { x, y, width, height: barHeight, r: 2 },
            style: { fill: getStateColor(label), stroke: 'none' },
          };
        },
        encode: { x: [1, 2], y: 0 },
        data: segments.map((segment) => [row, segment.start, segment.end, segment.label]),
        animation: false,
      },
    ],
    tooltip: { show: false },
    animation: false,
  };
};

const isBinaryLikeEntityData = (entityData?: DashboardEntityData) => {
  if (!entityData) return false;
  if (entityData.data_kind === 'binary') return true;
  if (entityData.render_mode !== 'state_timeline') return false;

  const labels = new Set<string>();
  (entityData.sparkline || []).forEach((point) => {
    const label = (point.state || '').toString().trim();
    if (label) labels.add(label.toLowerCase());
  });

  const latestLabel = (entityData.latest_point?.state || '').toString().trim();
  if (latestLabel) labels.add(latestLabel.toLowerCase());

  return labels.size > 0 && labels.size <= 2;
};

export const ValueWidget: React.FC<WidgetProps> = ({ deviceId, entityId, title, onRemove, onClick }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-data', deviceId, entityId],
    queryFn: async () => {
      const response = await api.get<DeviceDashboardResponse>(`/data/${deviceId}/dashboard`, {
        params: { entity_ids: entityId }
      });
      return response.data;
    },
    refetchInterval: 60000,
  });

  const entityData = data?.entities?.find(e => e.entity_id === entityId);
  const latestPoint = entityData?.latest_point;
  const value = latestPoint?.value;
  const state = latestPoint?.state;
  const isStale = entityData?.is_stale;

  return (
    <div 
      onClick={onClick}
      className={`bg-white p-6 rounded-2xl border border-slate-200 shadow-sm group hover:border-blue-300 transition-all ${onClick ? 'cursor-pointer active:scale-95' : ''}`}
    >
      <div className="flex justify-between items-start mb-4">
        <div className={`p-2 rounded-lg ${isStale ? 'bg-amber-50 text-amber-500' : 'bg-blue-50 text-blue-600'}`}>
          <Activity className="w-4 h-4" />
        </div>
        <button 
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }} 
          className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-red-500 transition"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      <div className="flex justify-between items-baseline mb-1">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider truncate mr-2" title={title}>{title}</h4>
        {entityData?.freshness_info && (
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${isStale ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-500'}`}>
            {entityData.freshness_info}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        {isLoading ? (
          <div className="h-8 w-24 bg-slate-100 animate-pulse rounded"></div>
        ) : value !== undefined ? (
          <>
            <span className={`text-3xl font-bold ${isStale ? 'text-slate-500' : 'text-slate-900'}`}>
              {typeof value === 'number' ? value.toLocaleString('de-DE') : value}
            </span>
            <span className="text-slate-400 text-sm font-medium">
              {state && String(state) !== String(value) ? state : ''}
            </span>
          </>
        ) : (
          <span className="text-slate-300 font-medium">Keine Daten</span>
        )}
      </div>
    </div>
  );
};

export const StatusWidget: React.FC<WidgetProps> = ({ deviceId, entityId, title, onRemove, onClick }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-data', deviceId, entityId],
    queryFn: async () => {
      const response = await api.get<DeviceDashboardResponse>(`/data/${deviceId}/dashboard`, {
        params: { entity_ids: entityId }
      });
      return response.data;
    },
    refetchInterval: 60000,
  });

  const entityData = data?.entities?.find(e => e.entity_id === entityId);
  const latestPoint = entityData?.latest_point;
  const normalizedState = (latestPoint?.state || '').toString().trim().toLowerCase();
  const truthyStates = new Set(['on', 'an', 'ein', 'active', 'heating', 'heizen', 'true', 'ja']);
  const isOn = latestPoint?.value === 1 || truthyStates.has(normalizedState);
  const hasData = latestPoint !== undefined;
  const isStale = entityData?.is_stale;

  return (
    <div 
      onClick={onClick}
      className={`bg-white p-6 rounded-2xl border border-slate-200 shadow-sm group hover:border-blue-300 transition-all ${onClick ? 'cursor-pointer active:scale-95' : ''}`}
    >
      <div className="flex justify-between items-start mb-4">
        <div className={`p-2 rounded-lg ${hasData ? (isOn ? 'bg-green-50 text-green-600' : 'bg-slate-50 text-slate-400') : 'bg-slate-50 text-slate-300'}`}>
          <AlertCircle className="w-4 h-4" />
        </div>
        <button 
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }} 
          className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-red-500 transition"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      <div className="flex justify-between items-baseline mb-1">
        <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider truncate mr-2" title={title}>{title}</h4>
        {entityData?.freshness_info && (
          <div className="flex flex-col items-end">
             <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${isStale ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-500'}`}>
                {entityData.freshness_info}
             </span>
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        {isLoading ? (
          <div className="h-8 w-32 bg-slate-100 animate-pulse rounded"></div>
        ) : hasData ? (
          <>
            <div className={`w-3 h-3 rounded-full ${isOn ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-slate-300'}`}></div>
            <span className={`text-xl font-bold ${isOn ? 'text-green-700' : 'text-slate-500'}`}>
              {isOn ? 'AKTIV' : 'AUS'}
            </span>
          </>
        ) : (
          <span className="text-slate-300 font-medium">Keine Daten</span>
        )}
      </div>
    </div>
  );
};

export const MiniChartWidget: React.FC<WidgetProps> = ({ deviceId, entityId, title, onRemove, onClick }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-data', deviceId, entityId],
    queryFn: async () => {
      const response = await api.get<DeviceDashboardResponse>(`/data/${deviceId}/dashboard`, {
        params: { entity_ids: entityId }
      });
      return response.data;
    },
    refetchInterval: 60000,
  });

  const entityData = data?.entities?.find(e => e.entity_id === entityId);
  const latestPoint = entityData?.latest_point;
  const isBinary = entityData?.data_kind === 'binary';
  const isStateTimeline = entityData?.render_mode === 'state_timeline';
  const isBinaryLike = isBinaryLikeEntityData(entityData);
  const isStale = entityData?.is_stale;
  const { minTime, maxTime } = getSparklineRange();
  const sparklineData = buildSparklineSeriesData(entityData);
  const stateSegments = buildStateSparklineSegments(entityData, minTime, maxTime);
  const stateSparklineOptions = buildStateSparklineOptions(entityData, minTime, maxTime);
  const sparklineColor = isStale ? '#94a3b8' : (isBinary ? '#22c55e' : '#5468ff');
  const hasStateSegments = stateSegments.length > 0;
  const normalizedStateLabel = (latestPoint?.state || '').toString().trim();
  const latestDisplayValue = !latestPoint
    ? '-'
    : (isStateTimeline && normalizedStateLabel.length > 0)
      ? normalizedStateLabel
      : (typeof latestPoint.value === 'number'
        ? (isBinary ? (latestPoint.value === 1 ? 'AN' : 'AUS') : latestPoint.value.toLocaleString('de-DE'))
        : (latestPoint.state || '-'));

  const chartOptions = {
    grid: { left: 0, right: 0, top: 8, bottom: 0 },
    xAxis: {
      type: 'time',
      show: false,
      min: minTime,
      max: maxTime,
      boundaryGap: false,
    },
    yAxis: { type: 'value', show: false, scale: true },
    series: [{
      data: sparklineData,
      type: 'line',
      smooth: false,
      step: false,
      showSymbol: false,
      connectNulls: false,
      areaStyle: {
        opacity: 0.08,
        color: sparklineColor,
      },
      lineStyle: { 
        width: 2,
        color: sparklineColor,
      },
    }],
    tooltip: { show: false },
    animation: false
  };

  const normalizedState = (latestPoint?.state || '').toString().trim().toLowerCase();
  const truthyStates = new Set(['on', 'an', 'ein', 'active', 'heating', 'heizen', 'true', 'ja']);
  const isOn = latestPoint?.value === 1 || truthyStates.has(normalizedState);
  const hasData = latestPoint !== undefined;

  if (isBinaryLike) {
    return (
      <div
        onClick={onClick}
        className={`bg-white p-6 rounded-2xl border border-slate-200 shadow-sm group hover:border-blue-300 transition-all ${onClick ? 'cursor-pointer active:scale-95' : ''}`}
      >
        <div className="flex justify-between items-start mb-4">
          <div className={`p-2 rounded-lg ${hasData ? (isOn ? 'bg-green-50 text-green-600' : 'bg-slate-50 text-slate-400') : 'bg-slate-50 text-slate-300'}`}>
            <AlertCircle className="w-4 h-4" />
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-red-500 transition"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
        <div className="flex justify-between items-baseline mb-1">
          <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider truncate mr-2" title={title}>{title}</h4>
          {entityData?.freshness_info && (
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${isStale ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-500'}`}>
              {entityData.freshness_info}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isLoading ? (
            <div className="h-8 w-32 bg-slate-100 animate-pulse rounded"></div>
          ) : hasData ? (
            <>
              <div className={`w-3 h-3 rounded-full ${isOn ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-slate-300'}`}></div>
              <span className={`text-xl font-bold ${isOn ? 'text-green-700' : 'text-slate-500'}`}>
                {isOn ? 'AKTIV' : 'AUS'}
              </span>
            </>
          ) : (
            <span className="text-slate-300 font-medium">Keine Daten</span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div 
      onClick={onClick}
      className={`bg-white p-6 rounded-2xl border border-slate-200 shadow-sm group hover:border-blue-300 transition-all flex flex-col h-full ${onClick ? 'cursor-pointer active:scale-95' : ''}`}
    >
      <div className="flex justify-between items-start mb-2">
        <h4 className="text-slate-500 text-[10px] font-bold uppercase tracking-wider truncate flex-1" title={title}>{title}</h4>
        <button 
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }} 
          className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-red-500 transition ml-2"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      <div className="flex justify-between items-baseline mb-2">
        <span className={`text-xl font-bold ${isStale ? 'text-slate-500' : 'text-slate-900'}`}>
          {latestDisplayValue}
        </span>
        {entityData?.freshness_info && (
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${isStale ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-400'}`}>
            {entityData.freshness_info}
          </span>
        )}
      </div>
      <div className="flex-1 min-h-[60px]">
        {isLoading ? (
          <div className="h-full w-full bg-slate-50 animate-pulse rounded-lg"></div>
        ) : isStateTimeline && hasStateSegments ? (
          <ReactECharts option={stateSparklineOptions} style={{ height: '100%', width: '100%' }} />
        ) : sparklineData.length > 0 ? (
          <ReactECharts option={chartOptions} style={{ height: '100%', width: '100%' }} />
        ) : (
          <div className="h-full w-full flex items-center justify-center border border-dashed border-slate-100 rounded-lg">
             <span className="text-[10px] text-slate-300">Kein Verlauf</span>
          </div>
        )}
      </div>
    </div>
  );
};
