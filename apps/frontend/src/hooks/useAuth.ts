import { create } from 'zustand';
import type { User } from '../types/api';
import api from '../lib/api';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('token'),
  isLoading: true,
  login: async (token: string) => {
    localStorage.setItem('token', token);
    set({ isAuthenticated: true, isLoading: true });
    try {
      const response = await api.get<User>('/auth/me');
      set({ user: response.data, isLoading: false });
    } catch (error) {
      localStorage.removeItem('token');
      set({ isAuthenticated: false, user: null, isLoading: false });
      throw error;
    }
  },
  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, isAuthenticated: false, isLoading: false });
  },
  fetchMe: async () => {
    if (!localStorage.getItem('token')) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }
    try {
      const response = await api.get<User>('/auth/me');
      set({ user: response.data, isAuthenticated: true, isLoading: false });
    } catch (error) {
      localStorage.removeItem('token');
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
