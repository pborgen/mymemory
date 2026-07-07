"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  fetchPrompt,
  fetchPromptVersions,
  resetPrompt,
  rollbackPrompt,
  savePrompt,
} from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { PromptVersion } from "@/types";

export default function PromptEditor() {
  const router = useRouter();
  const params = useParams<{ key: string }>();
  const key = params.key;
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/login");
  }, [authLoading, isAuthenticated, router]);

  const { data: prompt, isLoading } = useQuery({
    queryKey: ["prompt", key],
    queryFn: () => fetchPrompt(key),
    enabled: isAuthenticated,
  });

  const { data: versions = [] } = useQuery({
    queryKey: ["prompt-versions", key],
    queryFn: () => fetchPromptVersions(key),
    enabled: isAuthenticated,
  });

  // Seed the editor with the active content once loaded.
  useEffect(() => {
    if (prompt && draft === null) setDraft(prompt.content);
  }, [prompt, draft]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["prompt", key] });
    queryClient.invalidateQueries({ queryKey: ["prompt-versions", key] });
    queryClient.invalidateQueries({ queryKey: ["prompts"] });
  };

  const save = useMutation({
    mutationFn: () => savePrompt(key, draft ?? ""),
    onSuccess: (p) => {
      setDraft(p.content);
      setError(null);
      invalidate();
    },
    onError: (e: Error) => setError(e.message),
  });

  const rollback = useMutation({
    mutationFn: (versionId: string) => rollbackPrompt(key, versionId),
    onSuccess: (p) => {
      setDraft(p.content);
      setError(null);
      invalidate();
    },
    onError: (e: Error) => setError(e.message),
  });

  const reset = useMutation({
    mutationFn: () => resetPrompt(key),
    onSuccess: (p) => {
      setDraft(p.content);
      setError(null);
      invalidate();
    },
    onError: (e: Error) => setError(e.message),
  });

  if (authLoading || !isAuthenticated || isLoading) {
    return (
      <div className="app-shell">
        <div className="fill-center">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  if (!prompt) {
    return (
      <div className="app-shell">
        <AppBar active="prompts" />
        <div className="container" style={{ flex: 1 }}>
          <p className="empty">Prompt not found.</p>
          <Link href="/admin/prompts">← Back to prompts</Link>
        </div>
      </div>
    );
  }

  const dirty = draft !== null && draft !== prompt.content;
  const busy = save.isPending || rollback.isPending || reset.isPending;

  return (
    <div className="app-shell">
      <AppBar active="prompts" />
      <div className="container" style={{ flex: 1 }}>
        <div style={{ paddingTop: 18 }}>
          <Link href="/admin/prompts" style={{ fontSize: 13 }}>
            ← Prompts
          </Link>
          <h1 style={{ fontSize: 22, margin: "8px 0 2px" }}>{prompt.name}</h1>
          <div className="meta">
            {prompt.key} · active v{prompt.activeVersion ?? "—"}
          </div>
          <p className="meta" style={{ marginTop: 6 }}>{prompt.description}</p>
          {prompt.variables.length > 0 && (
            <p className="meta">
              Template variables:{" "}
              {prompt.variables.map((v) => `{${v}}`).join(", ")}
            </p>
          )}
        </div>

        <textarea
          className="prompt-editor"
          value={draft ?? ""}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          rows={16}
        />

        {error && <p className="prompt-error">{error}</p>}

        <div className="prompt-actions">
          <button
            className="primary"
            onClick={() => save.mutate()}
            disabled={!dirty || busy || !(draft ?? "").trim()}
          >
            {save.isPending ? "Saving…" : "Save new version"}
          </button>
          <button
            onClick={() => setDraft(prompt.content)}
            disabled={!dirty || busy}
          >
            Discard changes
          </button>
          <button onClick={() => reset.mutate()} disabled={busy}>
            {reset.isPending ? "Resetting…" : "Reset to default"}
          </button>
        </div>

        <h2 style={{ fontSize: 16, marginTop: 28 }}>Version history</h2>
        <div className="mem-list">
          {versions.map((v) => (
            <VersionRow
              key={v.id}
              version={v}
              onRollback={() => rollback.mutate(v.id)}
              disabled={busy}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function VersionRow({
  version,
  onRollback,
  disabled,
}: {
  version: PromptVersion;
  onRollback: () => void;
  disabled: boolean;
}) {
  return (
    <div className="mem-row">
      <div className="body">
        <div className="content">
          v{version.version}
          {version.isActive && <span className="badge">active</span>}
        </div>
        <div className="meta">
          {version.createdBy || "system"} · {new Date(version.createdAt).toLocaleString()}
        </div>
        <div className="meta prompt-preview">{version.content}</div>
      </div>
      {!version.isActive && (
        <button className="del" onClick={onRollback} disabled={disabled}>
          Roll back
        </button>
      )}
    </div>
  );
}
