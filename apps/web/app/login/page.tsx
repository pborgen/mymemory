"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { fetchDevAccounts } from "@/api";
import { useAuth } from "@/auth";
import { Logo } from "@/Logo";

export default function Login() {
  const router = useRouter();
  const { isAuthenticated, isLoading, signInDev } = useAuth();
  const { data: devAccounts = [] } = useQuery({
    queryKey: ["devAccounts"],
    queryFn: fetchDevAccounts,
  });

  // Once auth resolves (or after a sign-in), bounce to the chat.
  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace("/chat");
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || isAuthenticated) {
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
      <div className="center-card">
        <div className="auth-card">
          <div style={{ marginBottom: 18 }}>
            <Logo iconSize={30} />
          </div>
          <h1>
            Tell it once.
            <br />
            Ask it anytime.
          </h1>
          <p className="sub">
            Say or type anything you want to remember — a license plate, a
            friend&apos;s address, a Wi-Fi password — then just ask for it later.
          </p>

          <div style={{ fontSize: 12, letterSpacing: 2, color: "var(--text-dim)", marginBottom: 12 }}>
            DEV SIGN-IN
          </div>
          {devAccounts.length === 0 ? (
            <p style={{ color: "var(--text-dim)", fontSize: 14 }}>
              No dev accounts found. Start the API with{" "}
              <code>ALLOW_DEV_AUTH_HEADERS=true</code> and make sure{" "}
              <code>NEXT_PUBLIC_API_URL</code> points to it.
            </p>
          ) : (
            devAccounts.map((acct) => (
              <button
                key={acct.email}
                className="acct"
                onClick={() => void signInDev(acct.email)}
              >
                <div className="name">{acct.name}</div>
                <div className="email">{acct.email}</div>
              </button>
            ))
          )}

          <p style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 24, lineHeight: 1.5 }}>
            Google sign-in is wired on the backend (POST /api/auth/google). Add a
            Google OAuth flow here to enable production login.
          </p>
        </div>
      </div>
    </div>
  );
}
