import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './hooks/useAuth';
import PrivateRoute from './components/PrivateRoute';
import AppLayout from './components/AppLayout';

import { useQuery } from '@tanstack/react-query';
import api from './lib/api';
import type { Device, Tenant } from './types/api';

import { 
  Users, 
  Database, 
  ChevronRight
} from 'lucide-react';

const LoginPage = lazy(() => import('./features/LoginPage'));
const DeviceListPage = lazy(() => import('./features/DeviceListPage'));
const DeviceDetailPage = lazy(() => import('./features/DeviceDetailPage'));
const TenantsPage = lazy(() => import('./features/TenantsPage'));
const AnalysisPage = lazy(() => import('./features/AnalysisPage'));
const UserManagementPage = lazy(() => import('./features/UserManagementPage'));

const RouteLoader: React.FC = () => (
  <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6">
    <div className="flex flex-col items-center gap-4 text-center">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600"></div>
      <div>
        <p className="text-sm font-semibold text-slate-700">Ansicht wird geladen</p>
        <p className="text-xs text-slate-400">Die Seite wird gerade vorbereitet.</p>
      </div>
    </div>
  </div>
);

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
    queryKey: ['devices'],
    queryFn: async () => {
      if (!user) return [];
      const resp = await api.get<Device[]>('/devices/');
      return resp.data;
    },
    enabled: !!user,
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
        <Suspense fallback={<RouteLoader />}>
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
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
