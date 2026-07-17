"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  activatePrompt,
  evalPrompt,
  fetchPrompt,
  fetchPromptVersions,
  resetPrompt,
  rollbackPrompt,
  savePrompt,
} from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { PromptEvalReport, PromptVersion } from "@/types";

export default function PromptEditor() {
  const router = useRouter();
  const params = useParams<{ key: string }>();
  const key = params.key;
  const { isAuthenticated, isAdmin, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const [draft, setDraft] = useState<string | null>(null);
  const [changeNote, setChangeNote] = useState("");
  const [forceReason, setForceReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [evalReport, setEvalReport] = useState<PromptEvalReport | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/login");
    else if (!authLoading && isAuthenticated && !isAdmin) router.replace("/chat");
  }, [authLoading, isAuthenticated, isAdmin, router]);

  const { data: prompt, isLoading } = useQuery({
    queryKey: ["prompt", key],
    queryFn: () => fetchPrompt(key),
    enabled: isAuthenticated && isAdmin,
  });

  const { data: versions = [] } = useQuery({
    queryKey: ["prompt-versions", key],
    queryFn: () => fetchPromptVersions(key),
    enabled: isAuthenticated && isAdmin,
  });

  useEffect(() => {
    if (prompt && draft === null) setDraft(prompt.content);
  }, [prompt, draft]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["prompt", key] });
    queryClient.invalidateQueries({ queryKey: ["prompt-versions", key] });
    queryClient.invalidateQueries({ queryKey: ["prompts"] });
  };

  const onSaved = (activated: boolean) => {
    if (activated && prompt) setDraft(prompt.content);
    setChangeNote("");
    setForceReason("");
    setError(null);
    invalidate();
  };

  const saveDraft = useMutation({
    mutationFn: () =>
      savePrompt(key, draft ?? "", changeNote.trim(), { activate: false }),
    onSuccess: (p) => {
      setDraft(p.content);
      onSaved(false);
      setEvalReport(p.eval ?? null);
    },
    onError: (e: Error) => setError(e.message),
  });

  const saveActivate = useMutation({
    mutationFn: () =>
      savePrompt(key, draft ?? "", changeNote.trim(), {
        activate: true,
        forceReason: forceReason.trim() || undefined,
      }),
    onSuccess: (p) => {
      setDraft(p.content);
      onSaved(true);
      setEvalReport(p.eval ?? null);
    },
    onError: (e: Error) => setError(e.message),
  });

  const runEval = useMutation({
    mutationFn: () => evalPrompt(key, draft ?? ""),
    onSuccess: (report) => {
      setEvalReport(report);
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  const activate = useMutation({
    mutationFn: (versionId: string) =>
      activatePrompt(key, versionId, forceReason.trim() || undefined),
    onSuccess: (p) => {
      setDraft(p.content);
      setEvalReport(p.eval ?? null);
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

  if (authLoading || !isAuthenticated || !isAdmin || isLoading) {
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
  const canSave = !!(draft ?? "").trim() && !!changeNote.trim();
  const busy =
    saveDraft.isPending ||
    saveActivate.isPending ||
    runEval.isPending ||
    activate.isPending ||
    rollback.isPending ||
    reset.isPending;

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
          <p className="meta" style={{ marginTop: 6 }}>
            Lifecycle: edit → (optional) run eval → save draft or save &amp; activate.
            Activation runs the golden eval gate; use force reason only to override.
          </p>
        </div>

        <textarea
          className="prompt-editor"
          value={draft ?? ""}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          rows={16}
        />

        <label className="prompt-note-label" htmlFor="change-note">
          Change note <span className="meta">(required)</span>
        </label>
        <input
          id="change-note"
          className="prompt-note"
          type="text"
          value={changeNote}
          onChange={(e) => setChangeNote(e.target.value)}
          placeholder="e.g. Tighten refuse-if-unknown for mortgage demo"
          disabled={busy}
        />

        <label className="prompt-note-label" htmlFor="force-reason">
          Force reason{" "}
          <span className="meta">(only if overriding a failed eval)</span>
        </label>
        <input
          id="force-reason"
          className="prompt-note"
          type="text"
          value={forceReason}
          onChange={(e) => setForceReason(e.target.value)}
          placeholder="Optional — required to activate when eval fails"
          disabled={busy}
        />

        {error && <p className="prompt-error">{error}</p>}

        {evalReport && <EvalPanel report={evalReport} />}

        <div className="prompt-actions">
          <button
            onClick={() => runEval.mutate()}
            disabled={busy || !(draft ?? "").trim()}
          >
            {runEval.isPending ? "Evaluating…" : "Run eval"}
          </button>
          <button
            onClick={() => saveDraft.mutate()}
            disabled={!dirty || busy || !canSave}
          >
            {saveDraft.isPending ? "Saving…" : "Save draft"}
          </button>
          <button
            className="primary"
            onClick={() => saveActivate.mutate()}
            disabled={!dirty || busy || !canSave}
          >
            {saveActivate.isPending ? "Activating…" : "Save & activate"}
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
              disabled={busy}
              onActivate={() => activate.mutate(v.id)}
              onRollback={() => rollback.mutate(v.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function EvalPanel({ report }: { report: PromptEvalReport }) {
  return (
    <div
      className="mem-row"
      style={{
        marginTop: 14,
        borderColor: report.passed ? "var(--accent)" : "var(--danger)",
      }}
    >
      <div className="body">
        <div className="content">
          Eval: {report.skipped ? "skipped (no suite)" : report.passed ? "passed" : "failed"}
        </div>
        <div className="meta">{report.summary}</div>
        {report.results.map((r) => (
          <div key={r.id} className="meta">
            {r.passed ? "✓" : "✗"} {r.id}: {r.detail}
          </div>
        ))}
      </div>
    </div>
  );
}

function VersionRow({
  version,
  onActivate,
  onRollback,
  disabled,
}: {
  version: PromptVersion;
  onActivate: () => void;
  onRollback: () => void;
  disabled: boolean;
}) {
  return (
    <div className="mem-row">
      <div className="body">
        <div className="content">
          v{version.version}
          {version.isActive && <span className="badge">active</span>}
          {!version.isActive && <span className="meta"> · draft / inactive</span>}
        </div>
        <div className="meta">
          {version.createdBy || "system"} · {new Date(version.createdAt).toLocaleString()}
        </div>
        {version.changeNote ? (
          <div className="meta">Note: {version.changeNote}</div>
        ) : null}
        <div className="meta prompt-preview">{version.content}</div>
      </div>
      {!version.isActive && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button className="primary" onClick={onActivate} disabled={disabled}>
            Activate
          </button>
          <button className="del" onClick={onRollback} disabled={disabled}>
            Roll back
          </button>
        </div>
      )}
    </div>
  );
}
