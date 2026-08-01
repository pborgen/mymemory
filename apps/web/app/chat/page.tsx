"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { fetchSettings, sendMemoryChat } from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { ChatMessage } from "@/types";
import { useVoice } from "@/useVoice";

let idSeq = 0;
const nextId = () => `m${idSeq++}`;

const GREETING: ChatMessage = {
  id: "greeting",
  role: "assistant",
  content:
    "Hi! Tell me anything you want to remember — like “my car license plate is 8XYZ123” — and ask me for it whenever you need it.",
};

export default function Chat() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const queryClient = useQueryClient();
  const sessionId = useRef<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { available: voiceAvailable, listening, toggle, stop } = useVoice(setInput);

  const { data: settingsData } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: isAuthenticated,
  });
  const showSources = !!settingsData?.settings.showSources;

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace("/login");
  }, [isLoading, isAuthenticated, router]);

  const mutation = useMutation({
    mutationFn: (message: string) => sendMemoryChat(message, sessionId.current),
    onSuccess: (res) => {
      sessionId.current = res.sessionId;
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: res.answer,
          action: res.action,
          sources: res.sources,
          chips: res.chips,
          requestId: res.requestId,
        },
      ]);
      if (
        res.action === "stored" ||
        res.action === "forgotten" ||
        res.action === "updated"
      ) {
        queryClient.invalidateQueries({ queryKey: ["memories"] });
      }
      if (res.action === "reminded") {
        queryClient.invalidateQueries({ queryKey: ["reminders"] });
      }
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: `⚠️ ${err.message}` },
      ]);
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, mutation.isPending]);

  const sendText = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || mutation.isPending) return;
    if (listening) stop();
    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: trimmed }]);
    setInput("");
    mutation.mutate(trimmed);
  };

  const send = () => sendText(input);

  const onChip = (chipId: string) => {
    if (chipId === "undo") sendText("Forget the last memory you stored");
    else if (chipId === "ask") setInput("What do you remember about ");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="app-shell">
        <div className="fill-center">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppBar active="chat" />
      <div className="container chat-wrap">
        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-msgs">
            {messages.map((m) => (
              <Bubble
                key={m.id}
                message={m}
                showSources={showSources}
                onChip={onChip}
              />
            ))}
            {mutation.isPending && <div className="thinking">thinking…</div>}
          </div>
        </div>

        <div className="composer">
          {voiceAvailable ? (
            <button
              type="button"
              className="mic-btn"
              onClick={toggle}
              aria-label={listening ? "Stop listening" : "Speak into chat"}
              aria-pressed={listening}
              title={listening ? "Stop listening" : "Speak into chat"}
            >
              <MicIcon />
            </button>
          ) : null}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={listening ? "Listening…" : "Tell me or ask me…"}
            rows={1}
            className={listening ? "listening" : undefined}
          />
          <button
            type="button"
            className="send-btn"
            onClick={send}
            disabled={!input.trim() || mutation.isPending}
            aria-label="Send"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"
        stroke="currentColor"
        strokeWidth="1.8"
      />
      <path
        d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function actionTag(action: ChatMessage["action"]): string | null {
  switch (action) {
    case "stored":
      return "✓ Stored";
    case "recalled":
      return "↩ Recalled";
    case "forgotten":
      return "✕ Forgotten";
    case "updated":
      return "✎ Updated";
    case "reminded":
      return "⏰ Reminder";
    case "chat":
    case "blocked":
    case "error":
    case undefined:
      return null;
    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}

function Bubble({
  message,
  showSources,
  onChip,
}: {
  message: ChatMessage;
  showSources: boolean;
  onChip: (id: string) => void;
}) {
  const isUser = message.role === "user";
  const tag = actionTag(message.action);

  return (
    <div className={`bubble ${isUser ? "user" : "bot"}`}>
      {tag && <span className="tag">{tag}</span>}
      <div>{message.content}</div>
      {showSources && message.sources && message.sources.length > 0 ? (
        <div className="sources">
          <div style={{ marginBottom: 4, fontWeight: 600 }}>Why this answer</div>
          {message.sources.map((s) => (
            <div key={s.id}>• {s.content}</div>
          ))}
        </div>
      ) : null}
      {message.chips && message.chips.length > 0 ? (
        <div className="chat-chips">
          {message.chips.map((c) => (
            <button
              key={c.id}
              type="button"
              className="chat-chip"
              onClick={() => onChip(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
