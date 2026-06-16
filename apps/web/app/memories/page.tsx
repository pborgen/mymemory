"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { deleteMemory, fetchMemories } from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { Memory } from "@/types";

export default function Memories() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/login");
  }, [authLoading, isAuthenticated, router]);

  const { data: memories = [], isLoading } = useQuery({
    queryKey: ["memories"],
    queryFn: fetchMemories,
    enabled: isAuthenticated,
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memories"] }),
  });

  if (authLoading || !isAuthenticated) {
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
      <AppBar active="memories" />
      <div className="container" style={{ flex: 1 }}>
        <div className="app-bar" style={{ borderBottom: "none", height: "auto", paddingTop: 22 }}>
          <h1 style={{ fontSize: 24, margin: 0 }}>Your memories</h1>
        </div>

        {isLoading ? (
          <div className="fill-center">
            <div className="spinner" />
          </div>
        ) : memories.length === 0 ? (
          <p className="empty">
            Nothing saved yet. Head to the chat and tell me something to remember.
          </p>
        ) : (
          <div className="mem-list">
            {memories.map((m) => (
              <MemoryRow
                key={m.id}
                memory={m}
                onDelete={() => remove.mutate(m.id)}
                deleting={remove.isPending && remove.variables === m.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MemoryRow({
  memory,
  onDelete,
  deleting,
}: {
  memory: Memory;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <div className="mem-row">
      <div className="body">
        <div className="content">{memory.content}</div>
        <div className="meta">
          {memory.source} · {new Date(memory.createdAt).toLocaleDateString()}
        </div>
      </div>
      <button className="del" onClick={onDelete} disabled={deleting}>
        {deleting ? "…" : "Delete"}
      </button>
    </div>
  );
}
