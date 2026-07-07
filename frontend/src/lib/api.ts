import * as tokenStore from "./token-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
  isRetry = false,
): Promise<T> {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (options.headers) {
    new Headers(options.headers).forEach((value, key) => headers.set(key, value));
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  // Expired access token on an authenticated call: refresh once and retry.
  // Unauthenticated 401s (e.g. wrong login credentials) fall through.
  if (res.status === 401 && accessToken && !isRetry) {
    const fresh = await refreshSession();
    if (fresh) return request(path, options, fresh, true);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}) as Record<string, unknown>);
    const message =
      (body.error as string) ??
      (body.detail as string) ??
      Object.values(body).flat().join(" ") ??
      "Request failed";
    throw new ApiError(message || "Request failed", res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface User {
  id: string;
  email: string;
  username: string;
  language_preference: string;
  is_premium: boolean;
  created_at: string;
}

export interface ChatSession {
  id: string;
  title: string;
  platform: string;
  created_at: string;
  updated_at: string;
  last_message: string | null;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources: unknown[];
  created_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: Message[];
}

export interface RegisterInput {
  email: string;
  username: string;
  password: string;
  password2: string;
  language_preference?: string;
}

export function register(data: RegisterInput): Promise<User> {
  return request("/api/auth/register/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function login(email: string, password: string): Promise<AuthTokens> {
  return request("/api/auth/token/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// The backend rotates refresh tokens (ROTATE_REFRESH_TOKENS), so a successful
// refresh returns a new pair; both are persisted before the caller retries.
let refreshInFlight: Promise<string | null> | null = null;

/**
 * Exchange the stored refresh token for a new access token.
 *
 * Returns the new access token, or null when refresh is impossible.
 * Concurrent callers share one in-flight refresh. Tokens are cleared
 * (logging the user out) only when the backend definitively rejects the
 * refresh token — never on transient network failures.
 */
export function refreshSession(): Promise<string | null> {
  refreshInFlight ??= doRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

async function doRefresh(): Promise<string | null> {
  const tokens = tokenStore.getTokens();
  if (!tokens) return null;

  try {
    const data = await request<{ access: string; refresh?: string }>(
      "/api/auth/token/refresh/",
      { method: "POST", body: JSON.stringify({ refresh: tokens.refresh }) },
    );
    const next = { access: data.access, refresh: data.refresh ?? tokens.refresh };
    tokenStore.setTokens(next);
    return next.access;
  } catch (err) {
    if (err instanceof ApiError && [400, 401, 403].includes(err.status)) {
      tokenStore.setTokens(null);
    }
    return null;
  }
}

export function getMe(accessToken: string): Promise<User> {
  return request("/api/auth/me/", {}, accessToken);
}

export function listSessions(accessToken: string): Promise<ChatSession[]> {
  return request("/api/sessions/", {}, accessToken);
}

export function createSession(accessToken: string): Promise<ChatSession> {
  return request(
    "/api/sessions/",
    { method: "POST", body: JSON.stringify({}) },
    accessToken,
  );
}

export function getSession(
  accessToken: string,
  sessionId: string,
): Promise<ChatSessionDetail> {
  return request(`/api/sessions/${sessionId}/`, {}, accessToken);
}

export function deleteSession(accessToken: string, sessionId: string): Promise<void> {
  return request(
    `/api/sessions/${sessionId}/`,
    { method: "DELETE" },
    accessToken,
  );
}

export function sendMessage(
  accessToken: string,
  sessionId: string,
  content: string,
): Promise<{ user: Message; assistant: Message }> {
  return request(
    `/api/sessions/${sessionId}/messages/`,
    { method: "POST", body: JSON.stringify({ content }) },
    accessToken,
  );
}
