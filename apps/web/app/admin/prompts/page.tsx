"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { fetchPrompts } from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { Prompt } from "@/types";

export default function PromptsAdmin() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/login");
  }, [authLoading, isAuthenticated, router]);

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: fetchPrompts,
    enabled: isAuthenticated,
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
      <AppBar active="prompts" />
      <div className="container" style={{ flex: 1 }}>
        <div className="app-bar" style={{ borderBottom: "none", height: "auto", paddingTop: 22 }}>
          <h1 style={{ fontSize: 24, margin: 0 }}>Prompts</h1>
        </div>

        {isLoading ? (
          <div className="fill-center">
            <div className="spinner" />
          </div>
        ) : (
          <div className="mem-list">
            {prompts.map((p) => (
              <PromptRow key={p.key} prompt={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PromptRow({ prompt }: { prompt: Prompt }) {
  return (
    <Link href={`/admin/prompts/${prompt.key}`} className="mem-row" style={{ textDecoration: "none" }}>
      <div className="body">
        <div className="content">{prompt.name}</div>
        <div className="meta">
          {prompt.description}
        </div>
        <div className="meta" style={{ opacity: 0.7 }}>
          {prompt.key} · v{prompt.activeVersion ?? "—"}
          {prompt.variables.length > 0 && ` · vars: ${prompt.variables.join(", ")}`}
        </div>
      </div>
    </Link>
  );
}
