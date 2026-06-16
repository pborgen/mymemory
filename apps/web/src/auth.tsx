"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { loadAuth, persistAuth } from "./api";
import type { AuthState } from "./types";

interface AuthContextValue {
  user: AuthState | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signInDev: (email: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthState | null>(null);
  // Start "loading" so SSR and first client render agree (both null) until we
  // read localStorage in the effect — avoids a hydration mismatch.
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setUser(loadAuth());
    setIsLoading(false);
  }, []);

  const signInDev = useCallback((email: string) => {
    const state: AuthState = {
      email,
      devMode: true,
      authenticatedAt: new Date().toISOString(),
    };
    persistAuth(state);
    setUser(state);
  }, []);

  const signOut = useCallback(() => {
    persistAuth(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        signInDev,
        signOut,
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
