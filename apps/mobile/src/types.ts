export interface AuthState {
  email: string;
  idToken?: string;
  devMode?: boolean;
  authenticatedAt: string;
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

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: "stored" | "recalled";
  sources?: MemorySource[];
}
