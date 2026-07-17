"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { fetchMetricsSummary } from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";

export default function MetricsPage() {
  const router = useRouter();
  const { isAuthenticated, isAdmin, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/login");
    else if (!authLoading && isAuthenticated && !isAdmin) router.replace("/chat");
  }, [authLoading, isAuthenticated, isAdmin, router]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: () => fetchMetricsSummary(24),
    enabled: isAuthenticated && isAdmin,
    refetchInterval: 15_000,
  });

  if (authLoading || !isAuthenticated || !isAdmin) {
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
      <AppBar active="metrics" />
      <div className="container" style={{ flex: 1, paddingTop: 18 }}>
        <h1 style={{ fontSize: 22, margin: "0 0 6px" }}>Chat metrics</h1>
        <p className="meta">
          Last 24 hours from <code>chat_metrics</code> — empty-retrieval and
          latency breakdown matter more than HTTP 200 for RAG quality.
        </p>

        {isLoading && <p className="empty">Loading…</p>}
        {error && <p className="prompt-error">{(error as Error).message}</p>}

        {data && (
          <div className="mem-list" style={{ marginTop: 20 }}>
            <StatRow
              label="Requests"
              value={`${data.requests} (${data.errors} errors)`}
            />
            <StatRow
              label="Actions"
              value={`store ${data.actions.stored} · recall ${data.actions.recalled}`}
            />
            <StatRow
              label="Empty retrieval"
              value={String(data.emptyRetrieval)}
            />
            <StatRow
              label="Latency (ms)"
              value={`avg ${data.latencyMs.avgTotal} · p95 ${data.latencyMs.p95Total}`}
            />
            <StatRow
              label="Stage avg (ms)"
              value={`classify ${data.latencyMs.avgClassify} · retrieve ${data.latencyMs.avgRetrieve} · generate ${data.latencyMs.avgGenerate}`}
            />
            <StatRow
              label="Feedback"
              value={`👍 ${data.feedback.thumbsUp} · 👎 ${data.feedback.thumbsDown}`}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="mem-row">
      <div className="body">
        <div className="content">{label}</div>
        <div className="meta">{value}</div>
      </div>
    </div>
  );
}
