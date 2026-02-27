import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const AUTH_COOKIE = 'alice-api-key';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

/** Sync the API key to a cookie so the Next.js middleware can read it server-side. */
function syncAuthCookie(key: string | null) {
  if (typeof document === 'undefined') return;
  if (key) {
    document.cookie = `${AUTH_COOKIE}=${encodeURIComponent(key)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Strict`;
  } else {
    document.cookie = `${AUTH_COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Strict`;
  }
}

interface AuthState {
  apiKey: string | null;
  isAuthenticated: boolean;
  setApiKey: (key: string | null) => void;
  logout: () => void;
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
      setApiKey: (key) => {
        syncAuthCookie(key);
        set({ apiKey: key, isAuthenticated: key !== null });
      },
      logout: () => {
        syncAuthCookie(null);
        set({ apiKey: null, isAuthenticated: false });
      },
    }),
    {
      name: 'alice-auth',
      // NOTE: intentionally no onRehydrateStorage here.
      // Cookie is only written after explicit successful verification in the login form,
      // preventing stale keys from granting middleware access before re-validation.
    }
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
