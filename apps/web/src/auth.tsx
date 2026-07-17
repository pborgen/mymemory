"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { fetchMe, loadAuth, persistAuth } from "./api";
import type { AuthState } from "./types";

interface AuthContextValue {
  user: AuthState | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  signInDev: (email: string) => Promise<void>;
  signOut: () => void;
  refreshRole: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthState | null>(null);
  // Start "loading" so SSR and first client render agree (both null) until we
  // read localStorage in the effect — avoids a hydration mismatch.
  const [isLoading, setIsLoading] = useState(true);

  const applyRole = useCallback(async (state: AuthState): Promise<AuthState> => {
    try {
      const me = await fetchMe();
      const next = { ...state, email: me.email, isAdmin: me.isAdmin };
      persistAuth(next);
      return next;
    } catch {
      const next = { ...state, isAdmin: false };
      persistAuth(next);
      return next;
    }
  }, []);

  useEffect(() => {
    const existing = loadAuth();
    if (!existing) {
      setIsLoading(false);
      return;
    }
    void applyRole(existing).then((next) => {
      setUser(next);
      setIsLoading(false);
    });
  }, [applyRole]);

  const signInDev = useCallback(
    async (email: string) => {
      const state: AuthState = {
        email,
        devMode: true,
        authenticatedAt: new Date().toISOString(),
      };
      persistAuth(state);
      const next = await applyRole(state);
      setUser(next);
    },
    [applyRole],
  );

  const signOut = useCallback(() => {
    persistAuth(null);
    setUser(null);
  }, []);

  const refreshRole = useCallback(async () => {
    const existing = loadAuth();
    if (!existing) return;
    const next = await applyRole(existing);
    setUser(next);
  }, [applyRole]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isAdmin: !!user?.isAdmin,
        isLoading,
        signInDev,
        signOut,
        refreshRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
