import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";

import type {
  AuthState,
  ChatResponse,
  DevAccount,
  Memory,
  Prompt,
  PromptVersion,
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
