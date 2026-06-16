"use client";

import Link from "next/link";

import { useAuth } from "./auth";
import { Logo } from "./Logo";

// Shared top bar for the signed-in app screens (chat + memories).
export function AppBar({ active }: { active: "chat" | "memories" }) {
  const { signOut } = useAuth();
  return (
    <div className="container app-bar">
      <Link href="/">
        <Logo iconSize={24} />
      </Link>
      <div className="links">
        {active === "chat" ? (
          <Link href="/memories">Memories</Link>
        ) : (
          <Link href="/chat">Chat</Link>
        )}
        <button onClick={signOut}>Sign out</button>
      </div>
    </div>
  );
}
