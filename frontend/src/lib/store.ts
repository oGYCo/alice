import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  apiKey: string | null;
  setApiKey: (key: string | null) => void;
  isAuthenticated: boolean;
}

interface SidebarState {
  isOpen: boolean;
  width: number;
  toggleSidebar: () => void;
  setSidebarWidth: (width: number) => void;
  activeSourceId: number | null;
  setActiveSource: (id: number | null) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      apiKey: null,
      isAuthenticated: false,
      setApiKey: (key) => set({ apiKey: key, isAuthenticated: key !== null }),
    }),
    { name: 'alice-auth' }
  )
);

export const useSidebarStore = create<SidebarState>()((set) => ({
  isOpen: true,
  width: 280,
  toggleSidebar: () => set((s) => ({ isOpen: !s.isOpen })),
  setSidebarWidth: (width) => set({ width }),
  activeSourceId: null,
  setActiveSource: (id) => set({ activeSourceId: id }),
}));
