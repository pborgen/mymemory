// Shared API types — mirror of apps/mobile/src/types.ts.
export interface AuthState {
  email: string;
  idToken?: string;
  devMode?: boolean;
  authenticatedAt: string;
  /** From profiles.role — refreshed via /api/me. */
  isAdmin?: boolean;
}

export interface Profile {
  email: string;
  fullName: string;
  role: "user" | "admin";
  createdAt: string;
  isAdmin?: boolean;
}

export interface MetricsSummary {
  windowHours: number;
  requests: number;
  errors: number;
  actions: { stored: number; recalled: number };
  emptyRetrieval: number;
  latencyMs: {
    avgTotal: number;
    p95Total: number;
    avgClassify: number;
    avgRetrieve: number;
    avgGenerate: number;
  };
  feedback: { thumbsUp: number; thumbsDown: number };
}

export interface DevAccount {
  email: string;
  name: string;
}

export interface MemorySource {
  id: string;
  content: string;
  similarity: number;
}

export type FeatureFlag =
  | "quickChips"
  | "showSources"
  | "forgetByTopic"
  | "editCorrect"
  | "conflictDetection"
  | "timeAwareAnswers"
  | "entityCards"
  | "sensitiveLock"
  | "pasteInbox"
  | "importExport"
  | "reminders"
  | "whisperMic"
  | "iosIntegrations";

export type UserSettings = Record<FeatureFlag, boolean>;

export interface FeatureCatalogItem {
  key: FeatureFlag;
  group: string;
  subgroup?: string;
  name: string;
  description: string;
}

export interface SettingsResponse {
  settings: UserSettings;
  catalog: FeatureCatalogItem[];
  groupOrder?: string[];
  groups?: string[];
}

export interface Reminder {
  id: string;
  content: string;
  dueAt?: string | null;
  doneAt?: string | null;
  createdAt: string;
}

export interface ChatChip {
  id: string;
  label: string;
}

export interface ChatResponse {
  answer: string;
  action:
    | "stored"
    | "recalled"
    | "forgotten"
    | "updated"
    | "reminded"
    | "chat"
    | "blocked"
    | "error";
  sources: MemorySource[];
  chips?: ChatChip[];
  sessionId: string;
  requestId?: string;
  timingsMs?: Record<string, number>;
  emptyRetrieval?: boolean;
  /** Prompt keys → version pins used for this turn (prompt ops / debugging). */
  promptVersions?: Record<
    string,
    { version: number | null; versionId: string | null; source: string }
  >;
}

export interface MemoryEntity {
  id: string;
  name: string;
  key: string;
  type: string;
  memoryCount?: number;
}

export interface Memory {
  id: string;
  content: string;
  source: string;
  createdAt: string;
  entities?: MemoryEntity[];
}

export interface Prompt {
  key: string;
  name: string;
  description: string;
  variables: string[];
  content: string;
  activeVersion: number | null;
  updatedAt: string;
}

export interface PromptVersion {
  id: string;
  version: number;
  content: string;
  changeNote: string;
  createdAt: string;
  createdBy: string;
  isActive: boolean;
}

export interface PromptEvalCaseResult {
  id: string;
  passed: boolean;
  detail: string;
}

export interface PromptEvalReport {
  key: string;
  passed: boolean;
  skipped: boolean;
  threshold: number;
  passedCount: number;
  total: number;
  results: PromptEvalCaseResult[];
  summary: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: ChatResponse["action"];
  sources?: MemorySource[];
  chips?: ChatChip[];
  requestId?: string;
}
