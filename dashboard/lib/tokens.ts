// localStorage-backed JWT store with a tiny subscription mechanism so React
// can react to login/logout. Kept framework-free so the API client can read
// tokens without importing React.

import type { Token } from "./types";

const ACCESS_KEY = "aegis.access_token";
const REFRESH_KEY = "aegis.refresh_token";

type Listener = () => void;
const listeners = new Set<Listener>();

const isBrowser = typeof window !== "undefined";

export function getAccessToken(): string | null {
  return isBrowser ? window.localStorage.getItem(ACCESS_KEY) : null;
}

export function getRefreshToken(): string | null {
  return isBrowser ? window.localStorage.getItem(REFRESH_KEY) : null;
}

export function setTokens(token: Token): void {
  if (!isBrowser) return;
  window.localStorage.setItem(ACCESS_KEY, token.access_token);
  window.localStorage.setItem(REFRESH_KEY, token.refresh_token);
  emit();
}

export function clearTokens(): void {
  if (!isBrowser) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  emit();
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function emit(): void {
  listeners.forEach((l) => l());
}
