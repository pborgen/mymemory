// Browser API client for the MyMemory FastAPI backend. Mirrors
// apps/mobile/src/api.ts, but persists auth in localStorage instead of
// expo-secure-store. Safe to import from client components only.
import type {
  AuthState,
  ChatResponse,
  DevAccount,
  Memory,
  MemoryEntity,
  MetricsSummary,
  Profile,
  Prompt,
  PromptEvalReport,
  PromptVersion,
  Reminder,
  SettingsResponse,
  UserSettings,
} from "./types";

export const AUTH_KEY = "mymemory_auth_v1";

const API_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Cache the loaded auth so header construction stays synchronous.
let cachedAuth: AuthState | null = null;

export function loadAuth(): AuthState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(AUTH_KEY);
    cachedAuth = raw ? (JSON.parse(raw) as AuthState) : null;
  } catch {
    cachedAuth = null;
  }
  return cachedAuth;
}

export function persistAuth(auth: AuthState | null): void {
  cachedAuth = auth;
  if (typeof window === "undefined") return;
  if (auth) {
    window.localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
  } else {
    window.localStorage.removeItem(AUTH_KEY);
  }
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  // Re-read localStorage if the in-memory cache was cleared (e.g. HMR).
  const auth = cachedAuth ?? loadAuth();
  if (auth?.devMode) {
    h["x-user-email"] = auth.email;
  } else if (auth?.idToken) {
    h["Authorization"] = `Bearer ${auth.idToken}`;
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
    persistAuth(null);
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    let message = `API ${res.status}`;
    try {
      const data = (await res.json()) as {
        error?: string;
        eval?: { summary?: string; results?: { id: string; passed: boolean; detail: string }[] };
      };
      if (data?.error) message = data.error;
      if (data?.eval?.summary) message = `${message} (${data.eval.summary})`;
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
export const sendMemoryChat = (message: string, sessionId?: string, source = "web") =>
  apiFetch<ChatResponse>("POST", "/api/memory/chat", { message, sessionId, source });

// Memories
export const fetchMemories = (entityKey?: string) => {
  const q = entityKey ? `?entity=${encodeURIComponent(entityKey)}` : "";
  return apiFetch<Memory[]>("GET", `/api/memory${q}`);
};
export const fetchMemoryEntities = () =>
  apiFetch<MemoryEntity[]>("GET", "/api/memory/entities");
export const createMemory = (content: string) =>
  apiFetch<{ ok: boolean; memory: Memory }>("POST", "/api/memory", { content });
export const deleteMemory = (id: string) =>
  apiFetch<{ ok: boolean }>("DELETE", `/api/memory/${id}`);
export const addMemoryEntity = (
  memoryId: string,
  name: string,
  type: string = "other",
) =>
  apiFetch<{ ok: boolean; entity: MemoryEntity; entities: MemoryEntity[] }>(
    "POST",
    `/api/memory/${memoryId}/entities`,
    { name, type },
  );
export const removeMemoryEntity = (memoryId: string, entityId: string) =>
  apiFetch<{ ok: boolean; entities: MemoryEntity[] }>(
    "DELETE",
    `/api/memory/${memoryId}/entities/${entityId}`,
  );
export const renameMemoryEntity = (
  entityId: string,
  name: string,
  type?: string,
) =>
  apiFetch<{ ok: boolean; entity: MemoryEntity }>(
    "PATCH",
    `/api/memory/entities/${entityId}`,
    type ? { name, type } : { name },
  );
// Managed prompts
export const fetchPrompts = () => apiFetch<Prompt[]>("GET", "/api/prompts");
export const fetchPrompt = (key: string) =>
  apiFetch<Prompt>("GET", `/api/prompts/${key}`);
export const fetchPromptVersions = (key: string) =>
  apiFetch<PromptVersion[]>("GET", `/api/prompts/${key}/versions`);
export const savePrompt = (
  key: string,
  content: string,
  changeNote: string,
  opts?: { activate?: boolean; forceReason?: string },
) =>
  apiFetch<Prompt & { eval?: PromptEvalReport; activated?: boolean }>(
    "PUT",
    `/api/prompts/${key}`,
    {
      content,
      changeNote,
      activate: opts?.activate ?? true,
      forceReason: opts?.forceReason,
    },
  );
export const evalPrompt = (key: string, content: string) =>
  apiFetch<PromptEvalReport>("POST", `/api/prompts/${key}/eval`, { content });
export const activatePrompt = (
  key: string,
  versionId: string,
  forceReason?: string,
) =>
  apiFetch<Prompt & { eval?: PromptEvalReport; activated?: boolean }>(
    "POST",
    `/api/prompts/${key}/activate`,
    { versionId, forceReason },
  );
export const rollbackPrompt = (key: string, versionId: string) =>
  apiFetch<Prompt>("POST", `/api/prompts/${key}/rollback`, { versionId });
export const resetPrompt = (key: string) =>
  apiFetch<Prompt>("POST", `/api/prompts/${key}/reset`);

// Roles (DB-backed profiles.role)
export const fetchMe = () => apiFetch<Profile & { isAdmin: boolean }>("GET", "/api/me");
export const fetchAdmins = () => apiFetch<Profile[]>("GET", "/api/admins");
export const setAdminRole = (email: string, role: "admin" | "user") =>
  apiFetch<Profile>("PUT", `/api/admins/${encodeURIComponent(email)}`, { role });

export const fetchMetricsSummary = (hours = 24) =>
  apiFetch<MetricsSummary>("GET", `/api/metrics/summary?hours=${hours}`);

export const submitChatFeedback = (
  requestId: string,
  rating: 1 | -1,
  comment = "",
) =>
  apiFetch<{ ok: boolean }>("POST", "/api/memory/chat/feedback", {
    requestId,
    rating,
    comment,
  });

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

export const fetchReminders = () =>
  apiFetch<Reminder[]>("GET", "/api/reminders");

export const markReminderDone = (id: string) =>
  apiFetch<{ ok: boolean }>("POST", `/api/reminders/${id}/done`);

// Auth config + Google credential exchange
export const fetchAuthConfig = (): Promise<{ googleClientId: string | null }> =>
  fetch(`${API_URL}/api/auth/config`).then(
    (r) => r.json() as Promise<{ googleClientId: string | null }>,
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
    let message = "Google sign-in failed";
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
