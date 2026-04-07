import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import type { Tenant, Device } from '../types/api';
import { Users, Plus, ChevronDown, ChevronRight, Trash2, Key, Database, Copy, Check } from 'lucide-react';

const TenantsPage: React.FC = () => {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const queryClient = useQueryClient();

  const { data: tenants, isLoading, error } = useQuery({
    queryKey: ['tenants'],
    queryFn: async () => {
      const response = await api.get<Tenant[]>('/tenants/');
      return response.data;
    },
  });

  const deleteTenantMutation = useMutation({
    mutationFn: async (tenantId: number) => {
      await api.delete(`/tenants/${tenantId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
  });

  const createTenantMutation = useMutation({
    mutationFn: async (name: string) => {
      const resp = await api.post<Tenant>('/tenants/', { name });
      return resp.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div className="h-8 w-48 bg-slate-200 animate-pulse rounded"></div>
          <div className="h-10 w-32 bg-slate-200 animate-pulse rounded"></div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-8 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-slate-50 animate-pulse rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 p-6 rounded-xl">
        <h3 className="font-bold mb-2">Fehler beim Laden der Kunden</h3>
        <p>Die Kundenliste konnte nicht vom Server abgerufen werden.</p>
      </div>
    );
  }

  // Hilfsfunktionen
  const toggleExpanded = (tenantId: number) => {
    setExpanded((prev) => ({ ...prev, [tenantId]: !prev[tenantId] }));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Kundenverwaltung</h1>
          <p className="text-slate-500">Verwalten Sie Ihre Mandanten und deren Einstellungen.</p>
        </div>
        <button 
          onClick={() => {
            const name = prompt('Name des neuen Kunden:');
            if (name) createTenantMutation.mutate(name);
          }}
          disabled={createTenantMutation.isPending}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-lg font-medium transition flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          {createTenantMutation.isPending ? 'Wird angelegt...' : 'Kunde anlegen'}
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-6 py-4 text-sm font-semibold text-slate-600">Kunde</th>
                <th className="px-6 py-4 text-sm font-semibold text-slate-600">ID / Slug</th>
                <th className="px-6 py-4 text-sm font-semibold text-slate-600 text-right">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tenants && tenants.length > 0 ? (
                tenants.map((tenant) => (
                  <React.Fragment key={tenant.id}>
                    <tr 
                      className={`hover:bg-slate-50 transition cursor-pointer ${expanded[tenant.id] ? 'bg-slate-50' : ''}`}
                      onClick={() => toggleExpanded(tenant.id)}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="text-slate-400">
                            {expanded[tenant.id] ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                          </div>
                          <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-bold">
                            {tenant.name.charAt(0).toUpperCase()}
                          </div>
                          <span className="font-bold text-slate-900">{tenant.name}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-[10px] text-slate-400 font-mono">ID: {tenant.id}</div>
                        <div className="text-sm text-slate-500 font-mono">{tenant.slug}</div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex justify-end gap-2">
                          <button 
                            onClick={(e) => {
                              e.stopPropagation();
                              if (confirm(`Kunde "${tenant.name}" wirklich löschen? Alle Geräte dieses Kunden werden ebenfalls entfernt.`)) {
                                deleteTenantMutation.mutate(tenant.id);
                              }
                            }}
                            className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition" 
                            title="Löschen"
                          >
                            <Trash2 className="w-5 h-5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expanded[tenant.id] && (
                      <TenantDevicesRow 
                        tenantId={tenant.id} 
                        tenantName={tenant.name}
                        key={`devices-${tenant.id}`} 
                      />
                    )}
                  </React.Fragment>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center">
                    <div className="flex flex-col items-center gap-2 text-slate-400">
                      <Users className="w-12 h-12 mb-2 opacity-20" />
                      <p className="text-lg font-medium">Keine Kunden gefunden</p>
                      <p className="text-sm">Legen Sie Ihren ersten Kunden an, um zu starten.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// Unterkomponente: Geräte eines Tenants verwalten
const TenantDevicesRow: React.FC<{ tenantId: number; tenantName: string }> = ({ tenantId, tenantName }) => {
  const qc = useQueryClient();
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [fullTokens, setFullTokens] = useState<Record<number, string>>({});
  const [loadingTokens, setLoadingTokens] = useState<Record<number, boolean>>({});
  
  const [name, setName] = React.useState('');
  const [influx, setInflux] = React.useState(`ha_Input_${tenantName.replace(/\s+/g, '_').toLowerCase()}`);

  const fetchFullToken = async (deviceId: number) => {
    if (fullTokens[deviceId]) return;
    
    setLoadingTokens(prev => ({ ...prev, [deviceId]: true }));
    try {
      const response = await api.get<Device>(`/devices/${deviceId}/token`);
      if (response.data.influx_token) {
        setFullTokens(prev => ({ ...prev, [deviceId]: response.data.influx_token! }));
      }
    } catch (err) {
      console.error('Failed to fetch full token', err);
      alert('Token konnte nicht geladen werden.');
    } finally {
      setLoadingTokens(prev => ({ ...prev, [deviceId]: false }));
    }
  };

  const formatLastSeen = (dateStr?: string) => {
    if (!dateStr) return 'Nie';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Gerade eben';
    if (diffMins < 60) return `vor ${diffMins} Min.`;
    return date.toLocaleString('de-DE');
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const { data: devices, isLoading, error } = useQuery({
    queryKey: ['devices', tenantId],
    queryFn: async () => {
      const resp = await api.get<Device[]>(`/devices/`, { params: { tenant_id: tenantId } });
      return resp.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: { display_name: string; influx_database_name?: string }) => {
      // WICHTIG: source_type auf influxdb_v2 für HA Influx2 Integration
      // Retention ist fest auf 90d im Hintergrund
      const body = { 
        tenant_id: tenantId, 
        source_type: 'influxdb_v2', 
        is_active: true, 
        retention_policy: '90d',
        ...payload 
      };
      const resp = await api.post<Device>(`/devices/`, body);
      return resp.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['devices', tenantId] });
      setName('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (deviceId: number) => {
      await api.delete(`/devices/${deviceId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['devices', tenantId] });
    },
  });

  return (
    <tr className="bg-slate-50">
      <td colSpan={4} className="px-6 py-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">Geräte für diesen Kunden</h3>
          </div>

          {/* Gerät anlegen */}
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Anzeigename (z. B. HA1)"
                className="border border-slate-300 rounded px-3 py-2 text-sm w-full"
              />
              <input
                value={influx}
                onChange={(e) => setInflux(e.target.value)}
                placeholder="Influx-Datenbankname (Bucket)"
                className="border border-slate-300 rounded px-3 py-2 text-sm w-full"
              />
            </div>
            <div className="mt-3 flex justify-end">
              <button
                onClick={() => createMutation.mutate({ display_name: name, influx_database_name: influx || undefined })}
                disabled={!name || createMutation.isPending}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-lg text-sm"
              >
                {createMutation.isPending ? 'Legt an…' : 'Gerät anlegen'}
              </button>
            </div>
            {createMutation.isError && (
              <p className="text-red-600 text-sm mt-2">Gerät konnte nicht angelegt werden.</p>
            )}
            {createMutation.isSuccess && (
              <p className="text-green-700 text-sm mt-2">Gerät wurde angelegt. Falls Influx-Admin-Token gesetzt ist, wurde die Datenbank erstellt.</p>
            )}
          </div>

          {/* Geräteliste */}
          <div className="bg-white border border-slate-200 rounded-lg">
            {isLoading ? (
              <div className="p-4 text-slate-500 text-sm">Lade Geräte…</div>
            ) : error ? (
              <div className="p-4 text-red-600 text-sm">Geräte konnten nicht geladen werden.</div>
            ) : devices && devices.length > 0 ? (
              <ul className="divide-y divide-slate-200">
                {devices.map((d) => (
                    <li key={d.id} className="px-4 py-4 flex flex-col gap-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-2.5 h-2.5 rounded-full ${d.is_online ? 'bg-green-500 animate-pulse' : 'bg-slate-300'}`} title={d.is_online ? 'Online' : 'Offline'}></div>
                          <div>
                            <div className="font-bold text-slate-900 flex items-center gap-2">
                              {d.display_name}
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${d.is_online ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                {d.is_online ? 'Online' : 'Offline'}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-0.5">
                              Zuletzt gesehen: {formatLastSeen(d.last_seen)}
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            if (confirm(`Gerät "${d.display_name}" wirklich löschen? Dies entfernt nur den Eintrag, nicht die Influx-Daten.`)) {
                              deleteMutation.mutate(d.id);
                            }
                          }}
                          className="inline-flex items-center gap-2 text-red-600 hover:text-red-700 px-3 py-1.5 border border-red-100 hover:border-red-200 rounded-md text-xs font-medium transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Löschen
                        </button>
                      </div>

                      <div className="flex flex-col md:flex-row gap-4">
                        <div className="flex-1 text-xs text-slate-500 font-mono flex items-center gap-1.5">
                          <Database className="w-3 h-3 text-slate-400" /> {d.influx_database_name}
                        </div>
                      </div>

                      {/* Token-Box für das Gerät */}
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2 flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <Key className="w-3 h-3" /> InfluxDB Token für Home Assistant
                          </div>
                          <button 
                            onClick={() => fetchFullToken(d.id)}
                            disabled={loadingTokens[d.id] || !!fullTokens[d.id]}
                            className={`text-[9px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                              fullTokens[d.id] 
                                ? 'bg-green-100 border-green-200 text-green-700' 
                                : 'bg-white border-slate-200 text-slate-500 hover:text-blue-600 hover:border-blue-300'
                            }`}
                          >
                            {loadingTokens[d.id] ? 'LÄDT...' : fullTokens[d.id] ? 'VOLLSTÄNDIG' : '[VOLL ANZEIGEN]'}
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          <code className="bg-white border border-slate-200 px-3 py-2 rounded text-xs font-mono text-blue-700 flex-1 break-all">
                            {fullTokens[d.id] || d.influx_token || 'Token wird beim Anlegen generiert'}
                          </code>
                          {(fullTokens[d.id] || d.influx_token) && (
                            <button 
                              onClick={() => handleCopy(fullTokens[d.id] || d.influx_token!, `token-dev-${d.id}`)}
                              className="p-2 bg-white border border-slate-200 rounded-lg hover:border-blue-300 hover:text-blue-600 transition h-fit self-start"
                              title="Token kopieren"
                            >
                              {copiedId === `token-dev-${d.id}` ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4 text-slate-400" />}
                            </button>
                          )}
                        </div>
                      </div>
                    </li>
                ))}
              </ul>
            ) : (
              <div className="p-4 text-slate-500 text-sm">Noch keine Geräte vorhanden.</div>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
};

export default TenantsPage;
