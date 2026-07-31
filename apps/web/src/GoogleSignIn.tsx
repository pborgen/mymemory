"use client";

import { useEffect, useRef, useState } from "react";

import { exchangeGoogleCredential, fetchAuthConfig } from "@/api";
import { useAuth } from "@/auth";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: {
            client_id: string;
            callback: (resp: { credential: string }) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: Record<string, unknown>,
          ) => void;
        };
      };
    };
  }
}

/**
 * Google Identity Services button. Loads the GIS script once the API reports a
 * client id (so local Mac without GOOGLE_CLIENT_ID stays on dev sign-in only).
 */
export function GoogleSignInButton() {
  const { signInGoogle } = useAuth();
  const btnRef = useRef<HTMLDivElement>(null);
  const [clientId, setClientId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetchAuthConfig()
      .then((cfg) => {
        if (!cancelled) setClientId(cfg.googleClientId);
      })
      .catch((e) => {
        if (!cancelled) {
          setClientId("");
          setError(e instanceof Error ? e.message : "Could not load Google sign-in");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!clientId || !btnRef.current) return;

    const onCredential = async (resp: { credential: string }) => {
      setError(null);
      try {
        const { email } = await exchangeGoogleCredential(resp.credential);
        await signInGoogle(resp.credential, email);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Google sign-in failed");
      }
    };

    const render = () => {
      if (!btnRef.current || !window.google?.accounts?.id) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (r) => void onCredential(r),
      });
      btnRef.current.innerHTML = "";
      window.google.accounts.id.renderButton(btnRef.current, {
        type: "standard",
        theme: "outline",
        size: "large",
        text: "continue_with",
        shape: "pill",
        width: 320,
      });
      setReady(true);
    };

    if (window.google?.accounts?.id) {
      render();
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );
    if (existing) {
      existing.addEventListener("load", render);
      return () => existing.removeEventListener("load", render);
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = render;
    document.head.appendChild(script);
  }, [clientId, signInGoogle]);

  if (clientId === null) {
    return null; // still loading config
  }
  if (!clientId) {
    if (error) {
      return <p className="prompt-error">{error}</p>;
    }
    return null; // Google not configured on this API
  }

  return (
    <div className="google-signin">
      {!ready && (
        <p className="meta" style={{ marginBottom: 8 }}>
          Loading Google…
        </p>
      )}
      <div ref={btnRef} />
      {error && <p className="prompt-error">{error}</p>}
    </div>
  );
}
