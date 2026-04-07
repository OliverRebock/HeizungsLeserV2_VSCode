import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './hooks/useAuth';
import PrivateRoute from './components/PrivateRoute';
import AppLayout from './components/AppLayout';
import LoginPage from './features/LoginPage';
import DeviceListPage from './features/DeviceListPage';
import DeviceDetailPage from './features/DeviceDetailPage';
import TenantsPage from './features/TenantsPage';
import AnalysisPage from './features/AnalysisPage';
import UserManagementPage from './features/UserManagementPage';

import { useQuery } from '@tanstack/react-query';
import api from './lib/api';
import type { Device, Tenant } from './types/api';

import { 
  Users, 
  Database, 
  ChevronRight
} from 'lucide-react';

const Dashboard = () => {
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

  const { data: devices, isLoading: isDevicesLoading } = useQuery({
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

  if (isDevicesLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-24"></div>
          ))}
        </div>
        <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-100 h-32"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {isAdmin && (
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 hover:shadow-md transition">
            <h3 className="text-slate-500 text-sm font-medium mb-1">Aktive Kunden</h3>
            <p className="text-2xl font-bold text-slate-900">{tenants?.length ?? 0}</p>
          </div>
        )}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 hover:shadow-md transition">
          <h3 className="text-slate-500 text-sm font-medium mb-1">Registrierte Geräte</h3>
          <p className="text-2xl font-bold text-slate-900">{devices?.length ?? 0}</p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 hover:shadow-md transition">
          <h3 className="text-slate-500 text-sm font-medium mb-1">Datenpunkte heute</h3>
          <p className="text-2xl font-bold text-slate-900">Live</p>
        </div>
      </div>
      <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200">
        <h2 className="text-xl font-bold text-slate-900 mb-4">Willkommen bei Heizungsleser V2</h2>
        <p className="text-slate-600 mb-6">Wählen Sie ein Gerät aus der Navigation oder der Übersicht aus, um Details und Verläufe anzuzeigen.</p>
        
        {isAdmin && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Link to="/tenants" className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-xl hover:border-blue-400 hover:bg-blue-50 transition group">
              <div className="flex items-center gap-3">
                <div className="bg-white p-2 rounded-lg border border-slate-200 text-slate-400 group-hover:text-blue-600 group-hover:border-blue-200">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-bold text-slate-900">Kunden verwalten</p>
                  <p className="text-xs text-slate-500">Mandanten anlegen und bearbeiten</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-blue-500" />
            </Link>
            <Link to="/devices" className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-xl hover:border-blue-400 hover:bg-blue-50 transition group">
              <div className="flex items-center gap-3">
                <div className="bg-white p-2 rounded-lg border border-slate-200 text-slate-400 group-hover:text-blue-600 group-hover:border-blue-200">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-bold text-slate-900">Geräte-Übersicht</p>
                  <p className="text-xs text-slate-500">Alle Home-Assistant Instanzen</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-blue-500" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

const queryClient = new QueryClient();

const App: React.FC = () => {
  const fetchMe = useAuthStore((state) => state.fetchMe);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          
          <Route element={<PrivateRoute><AppLayout /></PrivateRoute>}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/devices" element={<DeviceListPage />} />
            <Route path="/devices/:deviceId" element={<DeviceDetailPage />} />
            <Route path="/tenants" element={<TenantsPage />} />
            <Route path="/users" element={<UserManagementPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
