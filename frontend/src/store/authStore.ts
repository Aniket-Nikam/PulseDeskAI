import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { Admin } from "../types";

interface AuthState {
  admin: Admin | null;
  accessToken: string | null;
  refreshToken: string | null;
  isHydrated: boolean;

  setAuth: (admin: Admin, access: string, refresh: string) => void;
  setTokens: (access: string, refresh: string) => void;
  setAdmin: (admin: Admin) => void;
  logout: () => void;
  setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      admin: null,
      accessToken: null,
      refreshToken: null,
      isHydrated: false,

      setAuth: (admin, access, refresh) =>
        set({
          admin,
          accessToken: access,
          refreshToken: refresh,
        }),

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),

      setAdmin: (admin) => set({ admin }),

      logout: () =>
        set({
          admin: null,
          accessToken: null,
          refreshToken: null,
        }),

      setHydrated: () => set({ isHydrated: true }),
    }),
    {
      name: "pulsedesk-auth-v2",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        admin: s.admin,
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated();
      },
    }
  )
);

// Selectors
export const selectIsAuthenticated = (s: AuthState) =>
  !!s.accessToken && !!s.admin;
