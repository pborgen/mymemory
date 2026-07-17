import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Redirect, Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  fetchPrompt,
  fetchPromptVersions,
  resetPrompt,
  rollbackPrompt,
  savePrompt,
} from "@/api";
import { useAuth } from "@/auth";
import { theme } from "@/theme";
import type { PromptVersion } from "@/types";

export default function PromptEditor() {
  const { key } = useLocalSearchParams<{ key: string }>();
  const promptKey = String(key);
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [draft, setDraft] = useState<string | null>(null);
  const [changeNote, setChangeNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: prompt, isLoading } = useQuery({
    queryKey: ["prompt", promptKey],
    queryFn: () => fetchPrompt(promptKey),
    enabled: isAuthenticated,
  });

  const { data: versions = [] } = useQuery({
    queryKey: ["prompt-versions", promptKey],
    queryFn: () => fetchPromptVersions(promptKey),
    enabled: isAuthenticated,
  });

  useEffect(() => {
    if (prompt && draft === null) setDraft(prompt.content);
  }, [prompt, draft]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["prompt", promptKey] });
    queryClient.invalidateQueries({ queryKey: ["prompt-versions", promptKey] });
    queryClient.invalidateQueries({ queryKey: ["prompts"] });
  };

  const onResult = (content: string) => {
    setDraft(content);
    setChangeNote("");
    setError(null);
    invalidate();
  };
  const onError = (e: Error) => setError(e.message);

  const save = useMutation({
    mutationFn: () => savePrompt(promptKey, draft ?? "", changeNote.trim()),
    onSuccess: (p) => onResult(p.content),
    onError,
  });
  const rollback = useMutation({
    mutationFn: (versionId: string) => rollbackPrompt(promptKey, versionId),
    onSuccess: (p) => onResult(p.content),
    onError,
  });
  const reset = useMutation({
    mutationFn: () => resetPrompt(promptKey),
    onSuccess: (p) => onResult(p.content),
    onError,
  });

  if (authLoading || isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }
  if (!isAuthenticated) return <Redirect href="/login" />;

  if (!prompt) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }} edges={["top"]}>
        <Stack.Screen options={{ headerShown: false }} />
        <Text style={{ color: theme.textDim, textAlign: "center", marginTop: 60 }}>
          Prompt not found.
        </Text>
      </SafeAreaView>
    );
  }

  const dirty = draft !== null && draft !== prompt.content;
  const busy = save.isPending || rollback.isPending || reset.isPending;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }} edges={["top"]}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 12,
          paddingHorizontal: 18,
          paddingBottom: 12,
          borderBottomColor: theme.border,
          borderBottomWidth: 1,
        }}
      >
        <Pressable hitSlop={8} onPress={() => router.back()}>
          <Text style={{ color: theme.accent, fontSize: 15 }}>‹ Prompts</Text>
        </Pressable>
        <Text style={{ color: theme.text, fontSize: 18, fontWeight: "700", flex: 1 }} numberOfLines={1}>
          {prompt.name}
        </Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
        <Text style={{ color: theme.textDim, fontSize: 12 }}>
          {prompt.key} · active v{prompt.activeVersion ?? "—"}
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 13, lineHeight: 18 }}>
          {prompt.description}
        </Text>
        {prompt.variables.length > 0 && (
          <Text style={{ color: theme.textDim, fontSize: 12 }}>
            Template variables: {prompt.variables.map((v) => `{${v}}`).join(", ")}
          </Text>
        )}

        <TextInput
          value={draft ?? ""}
          onChangeText={setDraft}
          multiline
          textAlignVertical="top"
          autoCapitalize="none"
          autoCorrect={false}
          style={{
            backgroundColor: theme.surface,
            borderColor: theme.border,
            borderWidth: 1,
            borderRadius: 14,
            color: theme.text,
            padding: 14,
            fontSize: 14,
            lineHeight: 20,
            minHeight: 220,
            fontFamily: "Menlo",
          }}
        />

        <Text style={{ color: theme.textDim, fontSize: 12 }}>
          Change note (required — why is this version shipping?)
        </Text>
        <TextInput
          value={changeNote}
          onChangeText={setChangeNote}
          placeholder="e.g. Tighten refuse-if-unknown"
          placeholderTextColor={theme.textDim}
          editable={!busy}
          style={{
            backgroundColor: theme.surface,
            borderColor: theme.border,
            borderWidth: 1,
            borderRadius: 10,
            color: theme.text,
            padding: 12,
            fontSize: 14,
          }}
        />

        {error && <Text style={{ color: theme.danger, fontSize: 13 }}>{error}</Text>}

        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
          <Btn
            label={save.isPending ? "Saving…" : "Save new version"}
            primary
            disabled={!dirty || busy || !(draft ?? "").trim() || !changeNote.trim()}
            onPress={() => save.mutate()}
          />
          <Btn
            label="Discard"
            disabled={!dirty || busy}
            onPress={() => setDraft(prompt.content)}
          />
          <Btn
            label={reset.isPending ? "Resetting…" : "Reset to default"}
            disabled={busy}
            onPress={() => reset.mutate()}
          />
        </View>

        <Text style={{ color: theme.text, fontSize: 16, fontWeight: "700", marginTop: 16 }}>
          Version history
        </Text>
        {versions.map((v) => (
          <VersionRow
            key={v.id}
            version={v}
            disabled={busy}
            onRollback={() => rollback.mutate(v.id)}
          />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function Btn({
  label,
  onPress,
  primary,
  disabled,
}: {
  label: string;
  onPress: () => void;
  primary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={{
        backgroundColor: primary ? theme.accent : theme.surface,
        borderColor: primary ? theme.accent : theme.border,
        borderWidth: 1,
        borderRadius: 10,
        paddingVertical: 9,
        paddingHorizontal: 16,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <Text style={{ color: primary ? "#1a1308" : theme.text, fontSize: 14, fontWeight: "600" }}>
        {label}
      </Text>
    </Pressable>
  );
}

function VersionRow({
  version,
  onRollback,
  disabled,
}: {
  version: PromptVersion;
  onRollback: () => void;
  disabled: boolean;
}) {
  return (
    <View
      style={{
        backgroundColor: theme.surface,
        borderColor: theme.border,
        borderWidth: 1,
        borderRadius: 14,
        padding: 14,
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 12,
      }}
    >
      <View style={{ flex: 1 }}>
        <Text style={{ color: theme.text, fontSize: 14, fontWeight: "600" }}>
          v{version.version}
          {version.isActive ? " · active" : ""}
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 11, marginTop: 3 }}>
          {version.createdBy || "system"} · {new Date(version.createdAt).toLocaleString()}
        </Text>
        {version.changeNote ? (
          <Text style={{ color: theme.textDim, fontSize: 12, marginTop: 4 }}>
            Note: {version.changeNote}
          </Text>
        ) : null}
        <Text style={{ color: theme.textDim, fontSize: 12, marginTop: 6 }} numberOfLines={3}>
          {version.content}
        </Text>
      </View>
      {!version.isActive && (
        <Pressable hitSlop={8} onPress={onRollback} disabled={disabled}>
          <Text style={{ color: theme.accent, fontSize: 13 }}>Roll back</Text>
        </Pressable>
      )}
    </View>
  );
}
