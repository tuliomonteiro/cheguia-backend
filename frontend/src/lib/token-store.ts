import type { AuthTokens } from "./api";

const STORAGE_KEY = "cheguia_tokens:v1";

type Listener = (tokens: AuthTokens | null) => void;

// In-memory copy is the source of truth; localStorage is best-effort
// persistence (private browsing, quota, SSR all degrade gracefully).
let cached: AuthTokens | null | undefined;
const listeners = new Set<Listener>();

export function getTokens(): AuthTokens | null {
  if (cached === undefined) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      cached = raw ? (JSON.parse(raw) as AuthTokens) : null;
    } catch {
      cached = null;
    }
  }
  return cached;
}

export function setTokens(tokens: AuthTokens | null) {
  cached = tokens;
  try {
    if (tokens) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage unavailable — auth just won't persist across reloads.
  }
  listeners.forEach((listener) => listener(tokens));
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
