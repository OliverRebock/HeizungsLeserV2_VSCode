import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { DeviceDataResponse } from '../types/api';
import ReactECharts from 'echarts-for-react';
import { Trash2, Activity, AlertCircle } from 'lucide-react';

interface WidgetProps {
  deviceId: string;
  entityId: string;
  title: string;
  onRemove: () => void;
  onClick?: () => void;
}

export const ValueWidget: React.FC<WidgetProps> = ({ deviceId, entityId, title, onRemove, onClick }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['latest-value', deviceId, entityId],
    queryFn: async () => {
      const response = await api.get<DeviceDataResponse>(`/data/${deviceId}/timeseries`, {
        params: { entity_ids: entityId, range: '1h' }
      });
      return response.data;
    },
    refetchInterval: 60000, // Every minute
  });

  const latestPoint = data?.series[0]?.points?.at(-1);
  const value = latestPoint?.value;
  const state = latestPoint?.state;

  return (
    <div 
      onClick={onClick}
      className={`bg-white p-6 rounded-2xl border border-slate-200 shadow-sm group hover:border-blue-300 transition-all ${onClick ? 'cursor-pointer active:scale-95' : ''}`}
    >
      <div className="flex justify-between items-start mb-4">
        <div className="bg-blue-50 p-2 rounded-lg text-blue-600">
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
      <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1 truncate" title={title}>{title}</h4>
      <div className="flex items-baseline gap-2">
        {isLoading ? (
          <div className="h-8 w-24 bg-slate-100 animate-pulse rounded"></div>
        ) : value !== undefined ? (
          <>
            <span className="text-3xl font-bold text-slate-900">{typeof value === 'number' ? value.toLocaleString('de-DE') : value}</span>
            <span className="text-slate-400 text-sm font-medium">{state && String(state) !== String(value) ? state : ''}</span>
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
    queryKey: ['latest-status', deviceId, entityId],
    queryFn: async () => {
      const response = await api.get<DeviceDataResponse>(`/data/${deviceId}/timeseries`, {
        params: { entity_ids: entityId, range: '1h' }
      });
      return response.data;
    },
    refetchInterval: 60000,
  });

  const latestPoint = data?.series[0]?.points?.at(-1);
  const isOn = latestPoint?.value === 1 || latestPoint?.state === 'on';
  const hasData = latestPoint !== undefined;

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
      <h4 className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1 truncate" title={title}>{title}</h4>
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
    queryKey: ['mini-chart', deviceId, entityId],
    queryFn: async () => {
      const response = await api.get<DeviceDataResponse>(`/data/${deviceId}/timeseries`, {
        params: { entity_ids: entityId, range: '24h' }
      });
      return response.data;
    },
  });

  const series = data?.series[0];
  const isBinary = series?.data_kind === 'binary';

  const chartOptions = {
    grid: { left: 0, right: 0, top: 10, bottom: 0 },
    xAxis: { type: 'time', show: false },
    yAxis: { type: 'value', show: false, scale: true },
    series: [{
      data: series?.points.map(p => [new Date(p.ts), p.value]) || [],
      type: 'line',
      smooth: !isBinary,
      step: isBinary ? 'end' : false,
      showSymbol: false,
      areaStyle: { opacity: 0.1, color: '#3b82f6' },
      lineStyle: { width: 2, color: '#3b82f6' },
    }],
    tooltip: { show: false }
  };

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
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-xl font-bold text-slate-900">
          {series?.points?.at(-1)?.value?.toLocaleString('de-DE') || '-'}
        </span>
      </div>
      <div className="flex-1 min-h-[60px]">
        {isLoading ? (
          <div className="h-full w-full bg-slate-50 animate-pulse rounded-lg"></div>
        ) : (
          <ReactECharts option={chartOptions} style={{ height: '100%', width: '100%' }} />
        )}
      </div>
    </div>
  );
};
