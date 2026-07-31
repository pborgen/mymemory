import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  Text,
  View,
} from "react-native";

import { exchangeGoogleCredential, fetchAuthConfig } from "@/api";
import { useAuth } from "@/auth";
import { theme } from "@/theme";

WebBrowser.maybeCompleteAuthSession();

function reversedGoogleScheme(clientId: string): string {
  const guid = clientId.replace(/\.apps\.googleusercontent\.com$/i, "");
  return `com.googleusercontent.apps.${guid}`;
}

function GoogleSignInInner({
  webClientId,
  iosClientId,
}: {
  webClientId: string;
  iosClientId?: string;
}) {
  const { signInGoogle } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // On iOS/Android the provider picks iosClientId/androidClientId; `clientId`
  // is the fallback so a web-only config still loads (may fail at Google until
  // an iOS client is created — see infra/GOOGLE_AUTH.md).
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest(
    {
      webClientId,
      iosClientId,
      clientId: webClientId,
      selectAccount: true,
    },
    iosClientId
      ? { native: `${reversedGoogleScheme(iosClientId)}:/oauthredirect` }
      : undefined,
  );

  useEffect(() => {
    if (response?.type !== "success") return;
    const idToken = response.params.id_token;
    if (!idToken) {
      setError("Google did not return an ID token");
      return;
    }
    let cancelled = false;
    setBusy(true);
    setError(null);
    void (async () => {
      try {
        const { email } = await exchangeGoogleCredential(idToken);
        if (!cancelled) await signInGoogle(idToken, email);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Google sign-in failed");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [response, signInGoogle]);

  const disabled = !request || busy;
  const needsIosClient = Platform.OS === "ios" && !iosClientId;

  return (
    <View>
      {needsIosClient ? (
        <Text
          style={{
            color: theme.textDim,
            fontSize: 13,
            lineHeight: 18,
            marginBottom: 12,
          }}
        >
          For reliable iPhone login, add an iOS OAuth client (bundle
          com.pborgen.mymemory) and set GOOGLE_IOS_CLIENT_ID on the API. See
          infra/GOOGLE_AUTH.md.
        </Text>
      ) : null}
      <Pressable
        disabled={disabled}
        onPress={() => {
          setError(null);
          void promptAsync();
        }}
        style={({ pressed }) => ({
          backgroundColor: pressed ? theme.surfaceAlt : theme.surface,
          borderColor: theme.border,
          borderWidth: 1,
          borderRadius: 14,
          paddingVertical: 16,
          paddingHorizontal: 18,
          opacity: disabled ? 0.5 : 1,
          alignItems: "center",
        })}
      >
        {busy ? (
          <ActivityIndicator color={theme.accent} />
        ) : (
          <Text style={{ color: theme.text, fontSize: 16, fontWeight: "600" }}>
            Continue with Google
          </Text>
        )}
      </Pressable>
      {error ? (
        <Text style={{ color: theme.danger, fontSize: 13, marginTop: 10 }}>{error}</Text>
      ) : null}
    </View>
  );
}

/**
 * Browser-based Google ID-token sign-in (expo-auth-session).
 * Uses the web client id from the API; optional iOS client when configured.
 */
export function GoogleSignInButton() {
  const [webClientId, setWebClientId] = useState<string | null>(null);
  const [iosClientId, setIosClientId] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchAuthConfig()
      .then((cfg) => {
        if (cancelled) return;
        setWebClientId(cfg.googleClientId);
        setIosClientId(cfg.googleIosClientId ?? undefined);
      })
      .catch((e) => {
        if (cancelled) return;
        setWebClientId("");
        setError(e instanceof Error ? e.message : "Could not load Google sign-in");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (webClientId === null) {
    return (
      <View style={{ paddingVertical: 12, alignItems: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }
  if (!webClientId) {
    return error ? (
      <Text style={{ color: theme.danger, fontSize: 13, marginTop: 8 }}>{error}</Text>
    ) : null;
  }

  return (
    <GoogleSignInInner webClientId={webClientId} iosClientId={iosClientId} />
  );
}
