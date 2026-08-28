// The organization the app is currently acting in.
//
// Sent as `X-Aegis-Org` on every request. Absent, the API falls back to the
// user's own organization — so a single-team customer never encounters this
// at all, and the header only appears once someone actually switches.
//
// Kept framework-free (like tokens.ts) so the API client can read it without
// importing React, with the same tiny subscription mechanism so the org
// switcher re-renders.

const ORG_KEY = "aegis.active_org";

type Listener = () => void;
const listeners = new Set<Listener>();

const isBrowser = typeof window !== "undefined";

export function getActiveOrg(): string | null {
  return isBrowser ? window.localStorage.getItem(ORG_KEY) : null;
}

export function setActiveOrg(slugOrId: string | null): void {
  if (!isBrowser) return;
  if (slugOrId) window.localStorage.setItem(ORG_KEY, slugOrId);
  else window.localStorage.removeItem(ORG_KEY);
  listeners.forEach((l) => l());
}

export function subscribeOrg(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
