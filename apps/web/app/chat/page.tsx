"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { sendMemoryChat } from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { ChatMessage } from "@/types";

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
        },
      ]);
      if (res.action === "stored") {
        queryClient.invalidateQueries({ queryKey: ["memories"] });
      }
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: `⚠️ ${err.message}` },
      ]);
    },
  });

  // Keep the conversation pinned to the latest message.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, mutation.isPending]);

  const send = () => {
    const text = input.trim();
    if (!text || mutation.isPending) return;
    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: text }]);
    setInput("");
    mutation.mutate(text);
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
              <Bubble key={m.id} message={m} />
            ))}
            {mutation.isPending && <div className="thinking">thinking…</div>}
          </div>
        </div>

        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Tell me or ask me…"
            rows={1}
          />
          <button
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

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const tag =
    message.action === "stored"
      ? "✓ Stored"
      : message.action === "recalled"
        ? "↩ Recalled"
        : null;

  return (
    <div className={`bubble ${isUser ? "user" : "bot"}`}>
      {tag && <span className="tag">{tag}</span>}
      <div>{message.content}</div>
      {message.sources && message.sources.length > 0 && (
        <div className="sources">
          {message.sources.map((s) => (
            <div key={s.id}>• {s.content}</div>
          ))}
        </div>
      )}
    </div>
  );
}
