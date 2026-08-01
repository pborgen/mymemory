import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Redirect } from "expo-router";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  Share,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  deleteAllMemories,
  exportMemoriesJson,
  fetchReminders,
  fetchSettings,
  importMemoriesText,
  markReminderDone,
  pasteInbox,
  updateSettings,
} from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import { theme } from "@/theme";
import type { FeatureCatalogItem, UserSettings } from "@/types";

const GROUP_BLURBS: Record<string, string> = {
  Looking: "What shows up in chat and on your Memories list.",
  "Smart chat": "How MyMemory understands edits, forgets, and answers.",
  Library: "Bring facts in, export them, or park follow-ups.",
  Devices: "Voice and Apple extras — keep off unless you need them.",
};

const DEFAULT_GROUP_ORDER = ["Looking", "Smart chat", "Library", "Devices"];

function buildGroups(
  catalog: FeatureCatalogItem[],
  order: string[],
): [string, FeatureCatalogItem[]][] {
  const map = new Map<string, FeatureCatalogItem[]>();
  for (const item of catalog) {
    const list = map.get(item.group) ?? [];
    list.push(item);
    map.set(item.group, list);
  }
  const known = order.filter((g) => map.has(g));
  const extras = [...map.keys()].filter((g) => !order.includes(g)).sort();
  return [...known, ...extras].map((g) => [g, map.get(g) ?? []]);
}

function subgroupBlocks(
  items: FeatureCatalogItem[],
): { title: string | null; items: FeatureCatalogItem[] }[] {
  const blocks: { title: string | null; items: FeatureCatalogItem[] }[] = [];
  for (const item of items) {
    const title = item.subgroup?.trim() || null;
    const last = blocks[blocks.length - 1];
    if (last && last.title === title) last.items.push(item);
    else blocks.push({ title, items: [item] });
  }
  return blocks;
}

function ToolPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <View
      style={{
        marginTop: 18,
        paddingTop: 16,
        borderTopColor: theme.border,
        borderTopWidth: 1,
        gap: 10,
      }}
    >
      <Text
        style={{
          color: theme.text,
          fontSize: 16,
          fontWeight: "700",
        }}
      >
        {title}
      </Text>
      {children}
    </View>
  );
}

export default function Settings() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [pasteText, setPasteText] = useState("");
  const [importText, setImportText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [activeGroup, setActiveGroup] = useState("Looking");

  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: isAuthenticated,
  });

  const settings = data?.settings;
  const catalog = data?.catalog ?? [];
  const groupOrder = data?.groups?.length
    ? data.groups
    : data?.groupOrder?.length
      ? data.groupOrder
      : DEFAULT_GROUP_ORDER;

  const groups = useMemo(
    () => buildGroups(catalog, groupOrder),
    [catalog, groupOrder],
  );

  useEffect(() => {
    if (groups.length && !groups.some(([g]) => g === activeGroup)) {
      setActiveGroup(groups[0][0]);
    }
  }, [groups, activeGroup]);

  const save = useMutation({
    mutationFn: (patch: Partial<UserSettings>) => updateSettings(patch),
    onSuccess: (res) => {
      queryClient.setQueryData(["settings"], res);
      setStatus("Synced");
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

  const enabledCount = Object.values(settings).filter(Boolean).length;
  const activeItems = groups.find(([g]) => g === activeGroup)?.[1] ?? [];
  const blocks = subgroupBlocks(activeItems);
  const groupIndex = Math.max(
    0,
    groups.findIndex(([g]) => g === activeGroup),
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }} edges={["top"]}>
      <AppBar active="settings" />

      <ScrollView contentContainerStyle={{ paddingHorizontal: 18, paddingBottom: 60 }}>
        <Text
          style={{
            color: theme.accent,
            fontSize: 42,
            fontWeight: "800",
            letterSpacing: -1.5,
            lineHeight: 44,
            marginTop: 16,
            marginBottom: 10,
          }}
        >
          MyMemory
        </Text>
        <Text
          style={{
            color: theme.text,
            fontSize: 26,
            fontWeight: "700",
            letterSpacing: -0.5,
            lineHeight: 32,
            marginBottom: 10,
          }}
        >
          Dial in{"\n"}
          <Text style={{ color: theme.accent }}>what stays quiet.</Text>
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 15, lineHeight: 22, marginBottom: 10 }}>
          Features stay off until you want them.
        </Text>
        <Text
          style={{
            color: theme.textDim,
            fontSize: 12,
            letterSpacing: 1.5,
            fontWeight: "700",
            marginBottom: 18,
          }}
        >
          {enabledCount} LIVE{status ? `  ·  ${status.toUpperCase()}` : ""}
        </Text>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ gap: 8, paddingBottom: 16 }}
        >
          {groups.map(([group], i) => {
            const selected = group === activeGroup;
            return (
              <Pressable
                key={group}
                onPress={() => setActiveGroup(group)}
                style={{
                  paddingHorizontal: 14,
                  paddingVertical: 10,
                  borderRadius: 10,
                  backgroundColor: selected ? theme.accentSoft : theme.surface,
                  borderColor: selected ? theme.accent : theme.border,
                  borderWidth: 1,
                }}
              >
                <Text
                  style={{
                    color: selected ? theme.accent : theme.textDim,
                    fontSize: 11,
                    fontWeight: "700",
                    letterSpacing: 1,
                    marginBottom: 2,
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </Text>
                <Text
                  style={{
                    color: selected ? theme.text : theme.textDim,
                    fontSize: 14,
                    fontWeight: selected ? "700" : "500",
                  }}
                >
                  {group}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        <View style={{ marginBottom: 8 }}>
          <View
            style={{
              flexDirection: "row",
              alignItems: "baseline",
              gap: 10,
              marginBottom: 8,
            }}
          >
            <Text
              style={{
                color: theme.accent,
                fontSize: 18,
                fontWeight: "700",
                letterSpacing: -0.5,
              }}
            >
              {String(groupIndex + 1).padStart(2, "0")}
            </Text>
            <Text style={{ color: theme.text, fontSize: 22, fontWeight: "700" }}>
              {activeGroup}
            </Text>
          </View>
          <Text style={{ color: theme.textDim, fontSize: 14, lineHeight: 20, marginBottom: 12 }}>
            {GROUP_BLURBS[activeGroup] ?? "Optional capabilities for this area."}
          </Text>

          {blocks.map((block) => (
            <View key={block.title ?? "default"} style={{ marginBottom: 8 }}>
              {block.title ? (
                <Text
                  style={{
                    color: theme.accent,
                    fontSize: 11,
                    letterSpacing: 1.5,
                    fontWeight: "700",
                    marginTop: 8,
                    marginBottom: 4,
                  }}
                >
                  {block.title.toUpperCase()}
                </Text>
              ) : null}
              {block.items.map((item) => (
                <View
                  key={item.key}
                  style={{
                    flexDirection: "row",
                    gap: 14,
                    alignItems: "center",
                    paddingVertical: 14,
                    borderBottomColor: theme.border,
                    borderBottomWidth: 1,
                  }}
                >
                  <View style={{ flex: 1 }}>
                    <Text
                      style={{
                        color: theme.text,
                        fontSize: 16,
                        fontWeight: "700",
                      }}
                    >
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
                    thumbColor={settings[item.key] ? theme.bg : theme.textDim}
                  />
                </View>
              ))}
            </View>
          ))}

          {activeGroup === "Library" && settings.pasteInbox ? (
            <ToolPanel title="Paste inbox">
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
              <ActionButton
                label="Save lines"
                onPress={async () => {
                  try {
                    const res = await pasteInbox(pasteText);
                    setPasteText("");
                    setStatus(`Saved ${res.count}`);
                    queryClient.invalidateQueries({ queryKey: ["memories"] });
                  } catch (e) {
                    setStatus(e instanceof Error ? e.message : "Paste failed");
                  }
                }}
              />
            </ToolPanel>
          ) : null}

          {activeGroup === "Library" && settings.importExport ? (
            <ToolPanel title="Import / export">
              <View style={{ flexDirection: "row", gap: 10, flexWrap: "wrap" }}>
                <ActionButton
                  label="Share JSON export"
                  onPress={async () => {
                    try {
                      const data = await exportMemoriesJson();
                      await Share.share({
                        message: JSON.stringify(data, null, 2),
                        title: "mymemory-export.json",
                      });
                      setStatus(`Exported ${data.count}`);
                    } catch (e) {
                      setStatus(e instanceof Error ? e.message : "Export failed");
                    }
                  }}
                />
                <ActionButton
                  label="Delete all"
                  danger
                  onPress={() => {
                    Alert.alert(
                      "Delete all memories?",
                      "This cannot be undone easily.",
                      [
                        { text: "Cancel", style: "cancel" },
                        {
                          text: "Delete",
                          style: "destructive",
                          onPress: async () => {
                            try {
                              const res = await deleteAllMemories();
                              setStatus(`Deleted ${res.deleted}`);
                              queryClient.invalidateQueries({
                                queryKey: ["memories"],
                              });
                            } catch (e) {
                              setStatus(
                                e instanceof Error ? e.message : "Delete failed",
                              );
                            }
                          },
                        },
                      ],
                    );
                  }}
                />
              </View>
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
              <ActionButton
                label="Import"
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
              />
            </ToolPanel>
          ) : null}

          {activeGroup === "Library" && settings.reminders ? (
            <ToolPanel title="Reminders">
              <Text style={{ color: theme.textDim, fontSize: 13, lineHeight: 18 }}>
                In chat: “remind me to call the lender tomorrow”.
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
                <Text style={{ color: theme.textDim }}>No open reminders.</Text>
              ) : null}
            </ToolPanel>
          ) : null}

          {activeGroup === "Devices" && settings.iosIntegrations ? (
            <ToolPanel title="iOS tips">
              <Text style={{ color: theme.textDim, lineHeight: 20 }}>
                Deep link mymemory://chat — wire a Shortcut or Siri phrase that opens
                Chat with a dictated fact.
              </Text>
            </ToolPanel>
          ) : null}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function ActionButton({
  label,
  onPress,
  danger,
}: {
  label: string;
  onPress: () => void;
  danger?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={{
        backgroundColor: theme.surface,
        borderColor: danger ? theme.danger : theme.border,
        borderWidth: 1,
        borderRadius: 12,
        paddingHorizontal: 14,
        paddingVertical: 12,
        alignItems: "center",
      }}
    >
      <Text
        style={{
          color: danger ? theme.danger : theme.text,
          fontWeight: "600",
        }}
      >
        {label}
      </Text>
    </Pressable>
  );
}
