import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import { type User, type Tenant } from '../types/api';
import { useAuthStore } from '../hooks/useAuth';
import { 
  Users, 
  UserPlus, 
  Edit2, 
  Trash2, 
  Key, 
  Search,
  CheckCircle,
  XCircle,
  Loader2,
  X
} from 'lucide-react';

const UserManagementPage: React.FC = () => {
  const { user: currentUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTenant, setSelectedTenant] = useState<string>('');
  
  // Modal states
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  
  // Form states
  const [formData, setFormData] = useState({
    email: '',
    full_name: '',
    password: '',
    password_confirm: '',
    role: 'tenant_user',
    tenant_id: '',
    is_active: true
  });
  
  const [resetPassword, setResetPassword] = useState('');

  const isAdmin = currentUser?.is_superuser;

  const { data: users, isLoading: isUsersLoading } = useQuery({
    queryKey: ['users', selectedTenant],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (selectedTenant) params.append('tenant_id', selectedTenant);
      const response = await api.get<User[]>(`/users/?${params.toString()}`);
      return response.data;
    },
  });

  const { data: tenants } = useQuery({
    queryKey: ['tenants'],
    queryFn: async () => {
      if (!isAdmin) return [];
      const response = await api.get<Tenant[]>('/tenants/');
      return response.data;
    },
    enabled: !!isAdmin,
  });

  const createUserMutation = useMutation({
    mutationFn: (newUser: any) => api.post('/users/', newUser),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsEditModalOpen(false);
      resetForm();
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => api.put(`/users/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsEditModalOpen(false);
      resetForm();
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: ({ id, password }: { id: number; password: string }) => 
      api.post(`/users/${id}/reset-password`, { new_password: password }),
    onSuccess: () => {
      setIsResetModalOpen(false);
      setResetPassword('');
      alert('Passwort erfolgreich zurückgesetzt');
    },
  });

  const resetForm = () => {
    setFormData({
      email: '',
      full_name: '',
      password: '',
      password_confirm: '',
      role: 'tenant_user',
      tenant_id: isAdmin ? '' : (currentUser?.tenants?.[0]?.tenant_id.toString() || ''),
      is_active: true
    });
    setEditingUser(null);
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    const mainTenant = user.tenants[0];
    setFormData({
      email: user.email,
      full_name: user.full_name || '',
      password: '', // Empty means no change
      password_confirm: '',
      role: mainTenant?.role || 'tenant_user',
      tenant_id: mainTenant?.tenant_id.toString() || '',
      is_active: user.is_active ?? true
    });
    setIsEditModalOpen(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (formData.password !== formData.password_confirm) {
      alert('Passwörter stimmen nicht überein!');
      return;
    }

    const payload = { ...formData, tenant_id: parseInt(formData.tenant_id) };
    // Remove confirm password from payload
    const { password_confirm, ...submitPayload } = payload;
    
    if (editingUser) {
      // Don't send empty password
      const submitData: any = { ...submitPayload };
      if (!submitData.password) delete submitData.password;
      updateUserMutation.mutate({ id: editingUser.id, data: submitData });
    } else {
      createUserMutation.mutate(submitPayload);
    }
  };

  const handleDelete = (id: number) => {
    if (window.confirm('Möchten Sie diesen Benutzer wirklich löschen?')) {
      deleteUserMutation.mutate(id);
    }
  };

  const filteredUsers = users?.filter(u => {
    if (!isAdmin) {
      // Rule: tenant_admin can only see tenant_users (or themselves)
      const targetIsSelf = u.id === currentUser?.id;
      const targetIsTenantUser = u.tenants.some(t => t.role === 'tenant_user');
      if (!targetIsSelf && !targetIsTenantUser) return false;
    }
    return u.email.toLowerCase().includes(searchTerm.toLowerCase()) || 
           (u.full_name && u.full_name.toLowerCase().includes(searchTerm.toLowerCase()));
  });

  const getRoleBadge = (role: string) => {
    switch(role) {
      case 'platform_admin': return <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-xs font-bold uppercase">Plattform Admin</span>;
      case 'tenant_admin': return <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-bold uppercase">Mandanten Admin</span>;
      default: return <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-xs font-bold uppercase">Benutzer</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg text-white">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Benutzerverwaltung</h1>
            <p className="text-slate-500 text-sm">Verwalten Sie Benutzer, Rollen und Zugriffsrechte.</p>
          </div>
        </div>
        <button 
          onClick={() => { resetForm(); setIsEditModalOpen(true); }}
          className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl font-bold transition shadow-sm"
        >
          <UserPlus className="w-5 h-5" />
          Benutzer anlegen
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input 
            type="text"
            placeholder="Nach Name oder E-Mail suchen..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        {isAdmin && (
          <select 
            className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg outline-none min-w-[200px]"
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
          >
            <option value="">Alle Mandanten</option>
            {tenants?.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isUsersLoading ? (
          <div className="p-12 flex flex-col items-center justify-center text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin mb-2" />
            <p>Benutzer werden geladen...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs font-bold uppercase tracking-wider">
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Benutzer</th>
                  <th className="px-6 py-4">Rolle / Mandant</th>
                  <th className="px-6 py-4 text-right">Aktionen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredUsers?.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-12 text-center text-slate-400">Keine Benutzer gefunden.</td>
                  </tr>
                ) : (
                  filteredUsers?.map(u => {
                    const isSelf = u.id === currentUser?.id;
                    const targetIsTenantUser = u.tenants.some(t => t.role === 'tenant_user');
                    const canEdit = isAdmin || (targetIsTenantUser && !isSelf); // self-edit usually via profile, but let's keep it consistent with backend
                    const canReset = isAdmin || targetIsTenantUser;
                    const canDelete = isAdmin || (targetIsTenantUser && !isSelf);

                    return (
                    <tr key={u.id} className="hover:bg-slate-50 transition">
                      <td className="px-6 py-4">
                        {u.is_active ? (
                          <div className="flex items-center gap-1.5 text-emerald-600 font-medium text-sm">
                            <CheckCircle className="w-4 h-4" /> Aktiv
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 text-slate-400 font-medium text-sm">
                            <XCircle className="w-4 h-4" /> Inaktiv
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-bold text-slate-900">{u.full_name || 'Kein Name'}</div>
                        <div className="text-sm text-slate-500">{u.email}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          {u.tenants.length > 0 ? u.tenants.map((t, idx) => (
                            <div key={idx} className="flex flex-col gap-1">
                              <div>{getRoleBadge(t.role)}</div>
                              <div className="text-xs text-slate-500 font-medium">{t.tenant_name}</div>
                            </div>
                          )) : (
                            u.is_superuser ? getRoleBadge('platform_admin') : <span className="text-xs text-slate-400 italic">Kein Mandant</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {canEdit && (
                            <button 
                              onClick={() => handleEdit(u)}
                              className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
                              title="Bearbeiten"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                          )}
                          {canReset && (
                            <button 
                              onClick={() => { setEditingUser(u); setIsResetModalOpen(true); }}
                              className="p-2 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition"
                              title="Passwort zurücksetzen"
                            >
                              <Key className="w-4 h-4" />
                            </button>
                          )}
                          {canDelete && (
                            <button 
                              onClick={() => handleDelete(u.id)}
                              className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                              title="Löschen"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit/Create Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-xl font-bold text-slate-900">
                {editingUser ? 'Benutzer bearbeiten' : 'Neuen Benutzer anlegen'}
              </h3>
              <button onClick={() => setIsEditModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-6 h-6" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm font-bold text-slate-700 mb-1">Anzeigename</label>
                  <input 
                    type="text" 
                    required
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    value={formData.full_name}
                    onChange={(e) => setFormData({...formData, full_name: e.target.value})}
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-bold text-slate-700 mb-1">E-Mail Adresse</label>
                  <input 
                    type="email" 
                    required
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-bold text-slate-700 mb-1">
                    {editingUser ? 'Neues Passwort (optional)' : 'Passwort'}
                  </label>
                  <input 
                    type="password" 
                    required={!editingUser}
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-bold text-slate-700 mb-1">
                    Passwort bestätigen
                  </label>
                  <input 
                    type="password" 
                    required={!editingUser || !!formData.password}
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    value={formData.password_confirm}
                    onChange={(e) => setFormData({...formData, password_confirm: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-1">Rolle</label>
                  <select 
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg outline-none"
                    value={formData.role}
                    onChange={(e) => setFormData({...formData, role: e.target.value})}
                  >
                    <option value="tenant_user">Benutzer</option>
                    {isAdmin && <option value="tenant_admin">Mandanten Admin</option>}
                    {isAdmin && <option value="platform_admin">Plattform Admin</option>}
                  </select>
                </div>
                {isAdmin && (
                  <div>
                    <label className="block text-sm font-bold text-slate-700 mb-1">Mandant</label>
                    <select 
                      required
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg outline-none"
                      value={formData.tenant_id}
                      onChange={(e) => setFormData({...formData, tenant_id: e.target.value})}
                    >
                      <option value="" disabled>Auswählen...</option>
                      {tenants?.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </div>
                )}
                <div className="col-span-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input 
                      type="checkbox" 
                      className="w-4 h-4 text-blue-600 rounded"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                    />
                    <span className="text-sm font-bold text-slate-700">Benutzer ist aktiv</span>
                  </label>
                </div>
              </div>
              <div className="pt-4 flex gap-3">
                <button 
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition"
                >
                  Abbrechen
                </button>
                <button 
                  type="submit"
                  disabled={createUserMutation.isPending || updateUserMutation.isPending}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition shadow-md flex items-center justify-center gap-2"
                >
                  {(createUserMutation.isPending || updateUserMutation.isPending) && <Loader2 className="w-4 h-4 animate-spin" />}
                  Speichern
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Password Reset Modal */}
      {isResetModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4 animate-in fade-in zoom-in duration-200">
            <div className="text-center space-y-2">
              <div className="mx-auto w-12 h-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mb-4">
                <Key className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-slate-900">Passwort zurücksetzen</h3>
              <p className="text-sm text-slate-500">Geben Sie ein neues Passwort für <b>{editingUser?.email}</b> ein.</p>
            </div>
            <div className="space-y-4">
              <input 
                type="password" 
                placeholder="Neues Passwort..."
                className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-amber-500 outline-none"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
              />
              <div className="flex gap-3">
                <button 
                  onClick={() => setIsResetModalOpen(false)}
                  className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl transition"
                >
                  Abbrechen
                </button>
                <button 
                  onClick={() => resetPasswordMutation.mutate({ id: editingUser!.id, password: resetPassword })}
                  disabled={!resetPassword || resetPasswordMutation.isPending}
                  className="flex-1 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl transition shadow-md disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {resetPasswordMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Zurücksetzen
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagementPage;
