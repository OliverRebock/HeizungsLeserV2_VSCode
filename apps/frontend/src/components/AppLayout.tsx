import React from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../hooks/useAuth';
import Logo from './Logo';
import { 
  LayoutDashboard, 
  Users, 
  Database, 
  LogOut, 
  Menu, 
  X,
  Brain
} from 'lucide-react';

const AppLayout: React.FC = () => {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isAdmin = user?.is_superuser || user?.tenants?.some(t => t.role === 'platform_admin') || user?.email === 'admin@example.com';
  const isTenantAdmin = user?.tenants?.some(t => t.role === 'tenant_admin');
  
  console.log('Current User Permissions:', { 
    email: user?.email, 
    is_superuser: user?.is_superuser, 
    tenants: user?.tenants,
    isAdmin, 
    isTenantAdmin 
  });

  const isDeviceDetail = location.pathname.startsWith('/devices/');

  const navItems = [
    { label: 'Dashboard', path: '/', icon: LayoutDashboard },
    { label: 'Geräte', path: '/devices', icon: Database },
    { label: 'KI-Analyse (Beta)', path: '/analysis', icon: Brain },
  ];

  if (isAdmin || isTenantAdmin) {
    navItems.push({ label: 'Benutzerverwaltung', path: '/users', icon: Users });
  }

  if (isAdmin) {
    navItems.push({ label: 'Kunden', path: '/tenants', icon: Users });
  }

  const getPageTitle = () => {
    if (isDeviceDetail) return 'Geräte-Detailansicht';
    const currentNavItem = navItems.find(i => i.path === location.pathname);
    if (currentNavItem) return currentNavItem.label;
    if (location.pathname === '/tenants') return 'Kundenverwaltung';
    return 'Heizungsleser V2';
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row overflow-hidden h-screen">
      {/* Sidebar - Desktop */}
      <aside className="hidden md:flex flex-col w-64 bg-slate-900 text-white shrink-0">
        <div className="p-6 border-b border-slate-800">
          <Logo variant="light" className="h-12" />
        </div>
        
        <nav className="flex-1 px-4 py-6 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                (location.pathname === item.path || (item.path === '/devices' && isDeviceDetail))
                  ? 'bg-blue-600 text-white' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span className="font-medium">{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-800">
          <div className="px-4 py-1 mb-2">
            <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">v2.3.6-stable</p>
          </div>
          <div className="px-4 py-3 mb-4">
            <p className="text-sm font-medium truncate">{user?.full_name || user?.email}</p>
            <p className="text-xs text-slate-500 truncate">{user?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
          >
            <LogOut className="w-5 h-5" />
            <span className="font-medium">Abmelden</span>
          </button>
        </div>
      </aside>

      {/* Header - Mobile */}
      <header className="md:hidden bg-slate-900 text-white p-4 flex items-center justify-between sticky top-0 z-[60] border-b border-slate-800 shadow-lg">
        <Logo variant="light" iconOnly className="h-8" />
        <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
          {isMobileMenuOpen ? <X /> : <Menu />}
        </button>
      </header>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <div className="md:hidden fixed inset-0 bg-slate-900 z-50 pt-20 px-6">
          <nav className="space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center gap-4 px-4 py-4 rounded-xl text-lg ${
                  (location.pathname === item.path || (item.path === '/devices' && isDeviceDetail))
                    ? 'bg-blue-600 text-white' 
                    : 'text-slate-400'
                }`}
              >
                <item.icon className="w-6 h-6" />
                <span>{item.label}</span>
              </Link>
            ))}
            <button
              onClick={handleLogout}
              className="flex items-center gap-4 w-full px-4 py-4 text-slate-400 text-lg"
            >
              <LogOut className="w-6 h-6" />
              <span>Abmelden</span>
            </button>
          </nav>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <header className="hidden md:flex h-16 bg-white border-b border-slate-200 items-center px-8 justify-between shrink-0">
          <h2 className="text-slate-800 font-semibold text-lg">
            {getPageTitle()}
          </h2>
        </header>
        <div className="p-4 md:p-8 flex-1 overflow-auto scroll-smooth">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default AppLayout;
