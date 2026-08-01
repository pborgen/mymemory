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
  sensitivity?: string;
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

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: ChatResponse["action"];
  sources?: MemorySource[];
  chips?: ChatChip[];
}
