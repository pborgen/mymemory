"use client";

import Link from "next/link";

import { useAuth } from "./auth";
import { Logo } from "./Logo";
import { ThemePicker } from "./theme";

// Shared top bar: primary app destinations | utilities | admin | account.
export function AppBar({
  active,
}: {
  active: "chat" | "memories" | "settings" | "prompts" | "users" | "metrics";
}) {
  const { signOut, isAdmin } = useAuth();

  return (
    <div className="container app-bar">
      <Link href="/" className="app-bar-brand" aria-label="MyMemory home">
        <Logo iconSize={24} />
      </Link>

      <nav className="app-bar-nav" aria-label="Primary">
        <Link
          href="/chat"
          className={active === "chat" ? "is-active" : undefined}
          aria-current={active === "chat" ? "page" : undefined}
        >
          Chat
        </Link>
        <Link
          href="/memories"
          className={active === "memories" ? "is-active" : undefined}
          aria-current={active === "memories" ? "page" : undefined}
        >
          Memories
        </Link>
      </nav>

      <div className="app-bar-tools">
        <Link
          href="/settings"
          className={active === "settings" ? "is-active" : undefined}
          aria-current={active === "settings" ? "page" : undefined}
        >
          Settings
        </Link>
        <ThemePicker />

        {isAdmin ? (
          <div className="app-bar-admin" role="group" aria-label="Admin">
            <span className="app-bar-admin-label">Admin</span>
            <Link
              href="/admin/prompts"
              className={active === "prompts" ? "is-active" : undefined}
              aria-current={active === "prompts" ? "page" : undefined}
            >
              Prompts
            </Link>
            <Link
              href="/admin/users"
              className={active === "users" ? "is-active" : undefined}
              aria-current={active === "users" ? "page" : undefined}
            >
              Admins
            </Link>
            <Link
              href="/admin/metrics"
              className={active === "metrics" ? "is-active" : undefined}
              aria-current={active === "metrics" ? "page" : undefined}
            >
              Metrics
            </Link>
          </div>
        ) : null}

        <button type="button" className="app-bar-signout" onClick={signOut}>
          Sign out
        </button>
      </div>
    </div>
  );
}
