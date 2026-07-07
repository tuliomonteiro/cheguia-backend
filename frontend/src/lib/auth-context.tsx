"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import * as api from "./api";

const STORAGE_KEY = "cheguia_tokens:v1";

function readStoredTokens(): api.AuthTokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeStoredTokens(tokens: api.AuthTokens | null) {
  try {
    if (tokens) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage unavailable (private browsing, quota, disabled) — auth just won't persist.
  }
}

interface AuthContextValue {
  user: api.User | null;
  accessToken: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: api.RegisterInput) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<api.User | null>(null);
  const [loading, setLoading] = useState(
    () => typeof window !== "undefined" && readStoredTokens() !== null,
  );

  useEffect(() => {
    const tokens = readStoredTokens();
    if (!tokens) return;
    api
      .getMe(tokens.access)
      .then((me) => {
        setAccessToken(tokens.access);
        setUser(me);
      })
      .catch(() => writeStoredTokens(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    const me = await api.getMe(tokens.access);
    writeStoredTokens(tokens);
    setAccessToken(tokens.access);
    setUser(me);
  }, []);

  const registerUser = useCallback(
    async (data: api.RegisterInput) => {
      await api.register(data);
      await login(data.email, data.password);
    },
    [login],
  );

  const logout = useCallback(() => {
    writeStoredTokens(null);
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, accessToken, loading, login, register: registerUser, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
