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
}

export interface Memory {
  id: string;
  content: string;
  source: string;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: "stored" | "recalled";
  sources?: MemorySource[];
}
