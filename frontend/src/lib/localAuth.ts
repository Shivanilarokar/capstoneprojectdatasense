export type LocalAuthProfile = Record<string, unknown>;

export type LocalAuthSession = {
  accessToken: string;
  profile: LocalAuthProfile;
};

const LOCAL_AUTH_STORAGE_KEY = "scn:local-auth";
const LOCAL_AUTH_EVENT = "scn:local-auth-changed";


function decodeBase64Url(input: string): string {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return window.atob(padded);
}


function parseJwtProfile(accessToken: string): LocalAuthProfile {
  const [, payload = ""] = accessToken.split(".");
  if (!payload) {
    throw new Error("JWT payload is missing.");
  }
  return JSON.parse(decodeBase64Url(payload)) as LocalAuthProfile;
}


function parseExpiry(profile: LocalAuthProfile): number | null {
  const raw = profile.exp;
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  if (typeof raw === "string" && raw.trim()) {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}


function broadcastAuthChange() {
  window.dispatchEvent(new Event(LOCAL_AUTH_EVENT));
}


export function readLocalAuthSession(): LocalAuthSession | null {
  const raw = window.localStorage.getItem(LOCAL_AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const session = JSON.parse(raw) as LocalAuthSession;
    const expiresAt = parseExpiry(session.profile);
    if (expiresAt !== null && expiresAt * 1000 <= Date.now()) {
      window.localStorage.removeItem(LOCAL_AUTH_STORAGE_KEY);
      return null;
    }
    return session;
  } catch {
    window.localStorage.removeItem(LOCAL_AUTH_STORAGE_KEY);
    return null;
  }
}


export function storeLocalAuthSession(accessToken: string): LocalAuthSession {
  const session = {
    accessToken,
    profile: parseJwtProfile(accessToken),
  };
  window.localStorage.setItem(LOCAL_AUTH_STORAGE_KEY, JSON.stringify(session));
  broadcastAuthChange();
  return session;
}


export function clearLocalAuthSession() {
  window.localStorage.removeItem(LOCAL_AUTH_STORAGE_KEY);
  broadcastAuthChange();
}


export function subscribeLocalAuthSession(listener: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === LOCAL_AUTH_STORAGE_KEY) {
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(LOCAL_AUTH_EVENT, listener);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(LOCAL_AUTH_EVENT, listener);
  };
}
