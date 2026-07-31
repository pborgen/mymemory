"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { fetchDevAccounts } from "@/api";
import { useAuth } from "@/auth";
import { GoogleSignInButton } from "@/GoogleSignIn";
import { Logo } from "@/Logo";
import { ThemePicker } from "@/theme";

export default function Login() {
  const router = useRouter();
  const { isAuthenticated, isLoading, signInDev } = useAuth();
  const { data: devAccounts = [] } = useQuery({
    queryKey: ["devAccounts"],
    queryFn: fetchDevAccounts,
  });

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace("/chat/");
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

          <GoogleSignInButton />

          {devAccounts.length > 0 && (
            <>
              <div
                style={{
                  fontSize: 12,
                  letterSpacing: 2,
                  color: "var(--text-dim)",
                  margin: "22px 0 12px",
                }}
              >
                DEV SIGN-IN
              </div>
              {devAccounts.map((acct) => (
                <button
                  key={acct.email}
                  className="acct"
                  onClick={() => void signInDev(acct.email)}
                >
                  <div className="name">{acct.name}</div>
                  <div className="email">{acct.email}</div>
                </button>
              ))}
            </>
          )}

          {devAccounts.length === 0 && (
            <p
              style={{
                color: "var(--text-dim)",
                fontSize: 13,
                marginTop: 16,
                lineHeight: 1.5,
              }}
            >
              Sign in with Google to open your private memory store.
            </p>
          )}

          <div
            style={{
              marginTop: 18,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <span
              style={{
                fontSize: 12,
                letterSpacing: 2,
                color: "var(--text-dim)",
              }}
            >
              THEME
            </span>
            <ThemePicker />
          </div>
        </div>
      </div>
    </div>
  );
}
