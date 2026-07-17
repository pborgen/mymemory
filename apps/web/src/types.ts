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

export interface ChatResponse {
  answer: string;
  action: "stored" | "recalled";
  sources: MemorySource[];
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

export interface Memory {
  id: string;
  content: string;
  source: string;
  createdAt: string;
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
  action?: "stored" | "recalled";
  sources?: MemorySource[];
  requestId?: string;
}
