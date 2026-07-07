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
): Promise<T> {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (options.headers) {
    new Headers(options.headers).forEach((value, key) => headers.set(key, value));
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

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

export function refreshAccessToken(refresh: string): Promise<{ access: string }> {
  return request("/api/auth/token/refresh/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
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
