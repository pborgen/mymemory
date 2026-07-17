"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchAdmins, setAdminRole } from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { Profile } from "@/types";

export default function AdminsPage() {
  const router = useRouter();
  const { isAuthenticated, isAdmin, isLoading: authLoading, refreshRole } = useAuth();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/login");
    else if (!authLoading && isAuthenticated && !isAdmin) router.replace("/chat");
  }, [authLoading, isAuthenticated, isAdmin, router]);

  const { data: admins = [], isLoading } = useQuery({
    queryKey: ["admins"],
    queryFn: fetchAdmins,
    enabled: isAuthenticated && isAdmin,
  });

  const grant = useMutation({
    mutationFn: () => setAdminRole(email.trim().toLowerCase(), "admin"),
    onSuccess: async () => {
      setEmail("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["admins"] });
      await refreshRole();
    },
    onError: (e: Error) => setError(e.message),
  });

  const revoke = useMutation({
    mutationFn: (target: string) => setAdminRole(target, "user"),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["admins"] });
      await refreshRole();
    },
    onError: (e: Error) => setError(e.message),
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
      <AppBar active="users" />
      <div className="container" style={{ flex: 1 }}>
        <div style={{ paddingTop: 18 }}>
          <h1 style={{ fontSize: 22, margin: "0 0 6px" }}>Admins</h1>
          <p className="meta">
            Roles live in the database (<code>profiles.role</code>). The env
            super admin is seeded on startup; other admins are granted here and
            can edit prompts.
          </p>
        </div>

        <div className="prompt-actions" style={{ marginTop: 18, alignItems: "center" }}>
          <input
            className="prompt-note"
            style={{ maxWidth: 320, marginTop: 0 }}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="user@example.com"
            disabled={grant.isPending}
          />
          <button
            className="primary"
            disabled={grant.isPending || !email.trim() || !email.includes("@")}
            onClick={() => grant.mutate()}
          >
            {grant.isPending ? "Granting…" : "Make admin"}
          </button>
        </div>

        {error && <p className="prompt-error">{error}</p>}

        <h2 style={{ fontSize: 16, marginTop: 28 }}>Current admins</h2>
        {isLoading ? (
          <p className="empty">Loading…</p>
        ) : (
          <div className="mem-list">
            {admins.map((a) => (
              <AdminRow
                key={a.email}
                profile={a}
                busy={revoke.isPending}
                onRevoke={() => revoke.mutate(a.email)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AdminRow({
  profile,
  onRevoke,
  busy,
}: {
  profile: Profile;
  onRevoke: () => void;
  busy: boolean;
}) {
  return (
    <div className="mem-row">
      <div className="body">
        <div className="content">{profile.email}</div>
        <div className="meta">
          {profile.fullName || "—"} · {profile.role}
        </div>
      </div>
      <button className="del" onClick={onRevoke} disabled={busy}>
        Revoke
      </button>
    </div>
  );
}
