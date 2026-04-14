import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { Admin } from "../types";

interface AuthState {
  admin: Admin | null;
  isHydrated: boolean;

  setAuth: (admin: Admin) => void;
  setAdmin: (admin: Admin) => void;
  logout: () => void;
  setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      admin: null,
      isHydrated: false,

      setAuth: (admin) =>
        set({
          admin,
        }),

      setAdmin: (admin) => set({ admin }),

      logout: () =>
        set({
          admin: null,
        }),

      setHydrated: () => set({ isHydrated: true }),
    }),
    {
      name: "pulsedesk-auth-v2",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        admin: s.admin,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated();
      },
    }
  )
);

// Selectors
export const selectIsAuthenticated = (s: AuthState) =>
  !!s.admin;
