import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { Device, Tenant } from '../types/api';
import { Database, Plus, ChevronRight, Power, Activity } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../hooks/useAuth';

const DeviceListPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.is_superuser;

  const { data: tenants } = useQuery({
    queryKey: ['tenants'],
    queryFn: async () => {
      if (!isAdmin) return [];
      const response = await api.get<Tenant[]>('/tenants/');
      return response.data;
    },
    enabled: !!user && isAdmin,
  });

  const { data: devices, isLoading, error } = useQuery({
    queryKey: ['devices', user?.id, user?.tenants],
    queryFn: async () => {
      if (!user) return [];

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
      } else if (!isAdmin && user.tenants && user.tenants.length > 0) {
        const allDevices: Device[] = [];
        const processedTenantIds = new Set<number>();
        
        for (const t of user.tenants) {
          const tid = (t as any).tenant_id || (t as any).id;
          if (!tid || processedTenantIds.has(tid)) continue;
          
          try {
            const resp = await api.get<Device[]>(`/devices/?tenant_id=${tid}`);
            allDevices.push(...resp.data);
            processedTenantIds.add(tid);
          } catch (e) {
            console.error(`Error loading devices for tenant ${tid}`, e);
          }
        }
        return allDevices;
      }
      return [];
    },
    enabled: !!user && (isAdmin ? !!tenants : true),
  });

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="flex justify-between items-center">
          <div className="space-y-2">
            <div className="h-8 bg-slate-200 rounded w-48"></div>
            <div className="h-4 bg-slate-100 rounded w-64"></div>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white rounded-xl h-48 border border-slate-100"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-600 p-6 rounded-xl border border-red-100">
        <h3 className="font-bold mb-2">Fehler beim Laden der Geräte</h3>
        <p>Die Verbindung zum Server konnte nicht hergestellt werden.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Geräteübersicht</h1>
          <p className="text-slate-500">Alle registrierten Home-Assistant Instanzen</p>
        </div>
        <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition shadow-sm">
          <Plus className="w-5 h-5" />
          <span>Neues Gerät</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {devices?.map((device) => (
          <Link
            key={device.id}
            to={`/devices/${device.id}`}
            className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 hover:shadow-md hover:border-blue-300 transition group"
          >
            <div className="flex justify-between items-start mb-4">
              <div className="bg-slate-100 p-3 rounded-xl text-slate-600 group-hover:bg-blue-50 group-hover:text-blue-600 transition">
                <Database className="w-6 h-6" />
              </div>
              <span className={`px-2 py-1 rounded text-xs font-semibold flex items-center gap-1 ${
                device.is_online ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
              }`}>
                {device.is_online && <Power className={`w-3 h-3 ${device.is_online ? 'animate-pulse' : ''}`} />}
                {device.is_online ? 'Online' : 'Offline'}
              </span>
            </div>
            
            <h3 className="text-lg font-bold text-slate-900 mb-1">{device.display_name}</h3>
            <p className="text-sm text-slate-500 mb-4 font-mono">{device.slug}</p>
            
            <div className="flex items-center justify-between pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2 text-slate-600 text-sm">
                <Activity className="w-4 h-4" />
                <span>Zeitreihen bereit</span>
              </div>
              <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-blue-500 transition translate-x-0 group-hover:translate-x-1" />
            </div>
          </Link>
        ))}

        {devices?.length === 0 && (
          <div className="col-span-full py-12 text-center bg-white rounded-xl border-2 border-dashed border-slate-200">
            <Database className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-900">Keine Geräte gefunden</h3>
            <p className="text-slate-500">Legen Sie Ihr erstes Gerät an, um Daten zu erfassen.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DeviceListPage;
