import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";

import type {
  AuthState,
  ChatResponse,
  DevAccount,
  Memory,
  Prompt,
  PromptVersion,
  Reminder,
  SettingsResponse,
  UserSettings,
} from "./types";

export const AUTH_KEY = "mymemory_auth_v1";

const API_URL: string =
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ??
  "http://localhost:8080";

// expo-secure-store is async; cache the loaded auth so header construction stays sync.
let cachedAuth: AuthState | null = null;

export async function loadAuth(): Promise<AuthState | null> {
  try {
    const raw = await SecureStore.getItemAsync(AUTH_KEY);
    cachedAuth = raw ? (JSON.parse(raw) as AuthState) : null;
  } catch {
    cachedAuth = null;
  }
  return cachedAuth;
}

export async function persistAuth(auth: AuthState | null): Promise<void> {
  cachedAuth = auth;
  if (auth) {
    await SecureStore.setItemAsync(AUTH_KEY, JSON.stringify(auth));
  } else {
    await SecureStore.deleteItemAsync(AUTH_KEY);
  }
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (cachedAuth?.devMode) {
    h["x-user-email"] = cachedAuth.email;
  } else if (cachedAuth?.idToken) {
    h["Authorization"] = `Bearer ${cachedAuth.idToken}`;
  }
  return h;
}

async function apiFetch<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: authHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    await persistAuth(null);
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    let message = `API ${res.status}`;
    try {
      const data = (await res.json()) as { error?: string };
      if (data?.error) message = data.error;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export type AuthConfig = {
  googleClientId: string | null;
  googleIosClientId: string | null;
};

export const fetchAuthConfig = (): Promise<AuthConfig> =>
  fetch(`${API_URL}/api/auth/config`).then(
    (r) => r.json() as Promise<AuthConfig>,
  );

export async function exchangeGoogleCredential(
  credential: string,
): Promise<{ email: string }> {
  const res = await fetch(`${API_URL}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  if (!res.ok) {
    let message = `API ${res.status}`;
    try {
      const data = (await res.json()) as { error?: string };
      if (data?.error) message = data.error;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  const data = (await res.json()) as { email: string };
  return { email: data.email };
}

// Dev accounts (only available when the API runs with ALLOW_DEV_AUTH_HEADERS=true)
export const fetchDevAccounts = (): Promise<DevAccount[]> =>
  fetch(`${API_URL}/api/dev/accounts`).then((r) =>
    r.ok ? (r.json() as Promise<DevAccount[]>) : [],
  );

// Memory chat
export const sendMemoryChat = (message: string, sessionId?: string, source = "chat") =>
  apiFetch<ChatResponse>("POST", "/api/memory/chat", { message, sessionId, source });

// Memories
export const fetchMemories = () => apiFetch<Memory[]>("GET", "/api/memory");
export const createMemory = (content: string) =>
  apiFetch<{ ok: boolean; memory: Memory }>("POST", "/api/memory", { content });
export const deleteMemory = (id: string) =>
  apiFetch<{ ok: boolean }>("DELETE", `/api/memory/${id}`);

export const fetchSettings = () =>
  apiFetch<SettingsResponse>("GET", "/api/settings");

export const updateSettings = (settings: Partial<UserSettings>) =>
  apiFetch<SettingsResponse>("PATCH", "/api/settings", { settings });

export const pasteInbox = (text: string) =>
  apiFetch<{ ok: boolean; count: number }>("POST", "/api/settings/paste-inbox", {
    text,
  });

export const exportMemoriesJson = () =>
  apiFetch<{ count: number; memories: Memory[] }>("GET", "/api/settings/export");

export const importMemoriesText = (text: string) =>
  apiFetch<{ ok: boolean; count: number }>("POST", "/api/settings/import", {
    text,
  });

export const deleteAllMemories = () =>
  apiFetch<{ ok: boolean; deleted: number }>("DELETE", "/api/settings/memories");

export const fetchReminders = () => apiFetch<Reminder[]>("GET", "/api/reminders");

export const markReminderDone = (id: string) =>
  apiFetch<{ ok: boolean }>("POST", `/api/reminders/${id}/done`);

// Managed prompts
export const fetchPrompts = () => apiFetch<Prompt[]>("GET", "/api/prompts");
export const fetchPrompt = (key: string) =>
  apiFetch<Prompt>("GET", `/api/prompts/${key}`);
export const fetchPromptVersions = (key: string) =>
  apiFetch<PromptVersion[]>("GET", `/api/prompts/${key}/versions`);
export const savePrompt = (key: string, content: string, changeNote: string) =>
  apiFetch<Prompt>("PUT", `/api/prompts/${key}`, { content, changeNote });
export const rollbackPrompt = (key: string, versionId: string) =>
  apiFetch<Prompt>("POST", `/api/prompts/${key}/rollback`, { versionId });
export const resetPrompt = (key: string) =>
  apiFetch<Prompt>("POST", `/api/prompts/${key}/reset`);
