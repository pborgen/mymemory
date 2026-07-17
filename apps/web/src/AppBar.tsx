"use client";

import Link from "next/link";

import { useAuth } from "./auth";
import { Logo } from "./Logo";

// Shared top bar for the signed-in app screens (chat + memories + admin).
export function AppBar({
  active,
}: {
  active: "chat" | "memories" | "prompts" | "users" | "metrics";
}) {
  const { signOut, isAdmin } = useAuth();
  return (
    <div className="container app-bar">
      <Link href="/">
        <Logo iconSize={24} />
      </Link>
      <div className="links">
        {active !== "chat" && <Link href="/chat">Chat</Link>}
        {active !== "memories" && <Link href="/memories">Memories</Link>}
        {isAdmin && active !== "prompts" && (
          <Link href="/admin/prompts">Prompts</Link>
        )}
        {isAdmin && active !== "users" && (
          <Link href="/admin/users">Admins</Link>
        )}
        {isAdmin && active !== "metrics" && (
          <Link href="/admin/metrics">Metrics</Link>
        )}
        <button onClick={signOut}>Sign out</button>
      </div>
    </div>
  );
}
