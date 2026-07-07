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
import * as tokenStore from "./token-store";

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
    () => typeof window !== "undefined" && tokenStore.getTokens() !== null,
  );

  // Keep React state in sync with the token store: a background refresh
  // rotates the access token, and a rejected refresh clears it (logout).
  useEffect(
    () =>
      tokenStore.subscribe((tokens) => {
        setAccessToken(tokens?.access ?? null);
        if (!tokens) setUser(null);
      }),
    [],
  );

  useEffect(() => {
    const tokens = tokenStore.getTokens();
    if (!tokens) return;
    // getMe transparently refreshes an expired access token, so a returning
    // user stays signed in for the refresh token's lifetime, not the access
    // token's.
    api
      .getMe(tokens.access)
      .then((me) => {
        setAccessToken(tokenStore.getTokens()?.access ?? tokens.access);
        setUser(me);
      })
      .catch(() => tokenStore.setTokens(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    const me = await api.getMe(tokens.access);
    tokenStore.setTokens(tokens);
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
    tokenStore.setTokens(null);
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
