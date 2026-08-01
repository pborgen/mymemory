import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Redirect } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  deleteAllMemories,
  fetchReminders,
  fetchSettings,
  importMemoriesText,
  markReminderDone,
  pasteInbox,
  updateSettings,
} from "@/api";
import { useAuth } from "@/auth";
import { theme } from "@/theme";
import type { FeatureFlag } from "@/types";

export default function Settings() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [pasteText, setPasteText] = useState("");
  const [importText, setImportText] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: isAuthenticated,
  });

  const settings = data?.settings;
  const catalog = data?.catalog ?? [];

  const groups = useMemo(() => {
    const map = new Map<string, typeof catalog>();
    for (const item of catalog) {
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return [...map.entries()];
  }, [catalog]);

  const save = useMutation({
    mutationFn: (patch: Partial<Record<FeatureFlag, boolean>>) =>
      updateSettings(patch),
    onSuccess: (res) => {
      queryClient.setQueryData(["settings"], res);
      setStatus("Saved");
    },
    onError: (e: Error) => setStatus(e.message),
  });

  const remindersQuery = useQuery({
    queryKey: ["reminders"],
    queryFn: fetchReminders,
    enabled: !!settings?.reminders && isAuthenticated,
  });

  if (authLoading || isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }
  if (!isAuthenticated) return <Redirect href="/login" />;
  if (!settings) return null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }} edges={["top"]}>
      <View
        style={{
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          paddingHorizontal: 18,
          paddingBottom: 12,
          borderBottomColor: theme.border,
          borderBottomWidth: 1,
        }}
      >
        <Text style={{ color: theme.text, fontSize: 20, fontWeight: "700" }}>
          Settings
        </Text>
        <Link href="/chat" asChild>
          <Pressable hitSlop={8}>
            <Text style={{ color: theme.accent, fontSize: 15 }}>Chat ›</Text>
          </Pressable>
        </Link>
      </View>

      <ScrollView contentContainerStyle={{ padding: 18, paddingBottom: 60, gap: 22 }}>
        <Text style={{ color: theme.textDim, fontSize: 15, lineHeight: 22 }}>
          Turn features on only when you want them — chat stays quiet by default.
        </Text>
        {status ? (
          <Text style={{ color: theme.accent, fontSize: 14 }}>{status}</Text>
        ) : null}

        {groups.map(([group, items]) => (
          <View key={group} style={{ gap: 12 }}>
            <Text
              style={{
                color: theme.textDim,
                fontSize: 12,
                letterSpacing: 2,
                fontWeight: "700",
              }}
            >
              {group.toUpperCase()}
            </Text>
            {items.map((item) => (
              <View
                key={item.key}
                style={{
                  flexDirection: "row",
                  gap: 14,
                  alignItems: "center",
                  paddingVertical: 8,
                  borderBottomColor: theme.border,
                  borderBottomWidth: 1,
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text style={{ color: theme.text, fontSize: 16, fontWeight: "600" }}>
                    {item.name}
                  </Text>
                  <Text
                    style={{
                      color: theme.textDim,
                      fontSize: 13,
                      lineHeight: 18,
                      marginTop: 4,
                    }}
                  >
                    {item.description}
                  </Text>
                </View>
                <Switch
                  value={settings[item.key]}
                  onValueChange={(v) => save.mutate({ [item.key]: v })}
                  trackColor={{ false: theme.border, true: theme.accent }}
                />
              </View>
            ))}
          </View>
        ))}

        {settings.pasteInbox ? (
          <View style={{ gap: 10 }}>
            <Text style={{ color: theme.textDim, fontSize: 12, letterSpacing: 2 }}>
              PASTE INBOX
            </Text>
            <TextInput
              value={pasteText}
              onChangeText={setPasteText}
              multiline
              placeholder="One fact per line…"
              placeholderTextColor={theme.textDim}
              style={{
                minHeight: 100,
                color: theme.text,
                backgroundColor: theme.surface,
                borderColor: theme.border,
                borderWidth: 1,
                borderRadius: 12,
                padding: 12,
                fontSize: 15,
              }}
            />
            <Pressable
              onPress={async () => {
                try {
                  const res = await pasteInbox(pasteText);
                  setPasteText("");
                  setStatus(`Saved ${res.count} memories`);
                  queryClient.invalidateQueries({ queryKey: ["memories"] });
                } catch (e) {
                  setStatus(e instanceof Error ? e.message : "Paste failed");
                }
              }}
              style={{
                backgroundColor: theme.surface,
                borderColor: theme.border,
                borderWidth: 1,
                borderRadius: 12,
                padding: 14,
                alignItems: "center",
              }}
            >
              <Text style={{ color: theme.text, fontWeight: "600" }}>Save lines</Text>
            </Pressable>
          </View>
        ) : null}

        {settings.importExport ? (
          <View style={{ gap: 10 }}>
            <Text style={{ color: theme.textDim, fontSize: 12, letterSpacing: 2 }}>
              IMPORT / EXPORT
            </Text>
            <TextInput
              value={importText}
              onChangeText={setImportText}
              multiline
              placeholder="Paste CSV or one fact per line…"
              placeholderTextColor={theme.textDim}
              style={{
                minHeight: 90,
                color: theme.text,
                backgroundColor: theme.surface,
                borderColor: theme.border,
                borderWidth: 1,
                borderRadius: 12,
                padding: 12,
                fontSize: 15,
              }}
            />
            <Pressable
              onPress={async () => {
                try {
                  const res = await importMemoriesText(importText);
                  setImportText("");
                  setStatus(`Imported ${res.count}`);
                  queryClient.invalidateQueries({ queryKey: ["memories"] });
                } catch (e) {
                  setStatus(e instanceof Error ? e.message : "Import failed");
                }
              }}
              style={{
                backgroundColor: theme.surface,
                borderColor: theme.border,
                borderWidth: 1,
                borderRadius: 12,
                padding: 14,
                alignItems: "center",
              }}
            >
              <Text style={{ color: theme.text, fontWeight: "600" }}>Import</Text>
            </Pressable>
            <Pressable
              onPress={async () => {
                try {
                  const res = await deleteAllMemories();
                  setStatus(`Deleted ${res.deleted}`);
                  queryClient.invalidateQueries({ queryKey: ["memories"] });
                } catch (e) {
                  setStatus(e instanceof Error ? e.message : "Delete failed");
                }
              }}
              style={{
                backgroundColor: theme.surface,
                borderColor: theme.danger,
                borderWidth: 1,
                borderRadius: 12,
                padding: 14,
                alignItems: "center",
              }}
            >
              <Text style={{ color: theme.danger, fontWeight: "600" }}>
                Delete all memories
              </Text>
            </Pressable>
          </View>
        ) : null}

        {settings.reminders ? (
          <View style={{ gap: 10 }}>
            <Text style={{ color: theme.textDim, fontSize: 12, letterSpacing: 2 }}>
              REMINDERS
            </Text>
            {(remindersQuery.data ?? []).map((r) => (
              <View
                key={r.id}
                style={{
                  flexDirection: "row",
                  justifyContent: "space-between",
                  gap: 12,
                  paddingVertical: 8,
                  borderBottomColor: theme.border,
                  borderBottomWidth: 1,
                }}
              >
                <Text style={{ color: theme.text, flex: 1 }}>{r.content}</Text>
                <Pressable
                  onPress={async () => {
                    await markReminderDone(r.id);
                    queryClient.invalidateQueries({ queryKey: ["reminders"] });
                  }}
                >
                  <Text style={{ color: theme.accent }}>Done</Text>
                </Pressable>
              </View>
            ))}
            {(remindersQuery.data ?? []).length === 0 ? (
              <Text style={{ color: theme.textDim }}>
                No open reminders. In chat: “remind me to …”
              </Text>
            ) : null}
          </View>
        ) : null}

        {settings.iosIntegrations ? (
          <View style={{ gap: 8 }}>
            <Text style={{ color: theme.textDim, fontSize: 12, letterSpacing: 2 }}>
              IOS TIPS
            </Text>
            <Text style={{ color: theme.textDim, lineHeight: 20 }}>
              Deep link: mymemory://chat — use Shortcuts / Siri to open Chat with a
              dictated fact, or pin a home-screen shortcut.
            </Text>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
