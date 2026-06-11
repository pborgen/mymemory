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
  signInDev: (email: string) => Promise<void>;
  signInGoogle: (idToken: string, email: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthState | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadAuth()
      .then(setUser)
      .finally(() => setIsLoading(false));
  }, []);

  const signInDev = useCallback(async (email: string) => {
    const state: AuthState = {
      email,
      devMode: true,
      authenticatedAt: new Date().toISOString(),
    };
    await persistAuth(state);
    setUser(state);
  }, []);

  const signInGoogle = useCallback(async (idToken: string, email: string) => {
    const state: AuthState = {
      email,
      idToken,
      authenticatedAt: new Date().toISOString(),
    };
    await persistAuth(state);
    setUser(state);
  }, []);

  const signOut = useCallback(async () => {
    await persistAuth(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        signInDev,
        signInGoogle,
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
