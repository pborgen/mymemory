import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Redirect } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { deleteMemory, fetchMemories, fetchSettings } from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import { theme } from "@/theme";
import type { Memory } from "@/types";

export default function Memories() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});

  const { data: settingsData } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: isAuthenticated,
  });
  const entityCards = !!settingsData?.settings.entityCards;
  const sensitiveLock = !!settingsData?.settings.sensitiveLock;

  const { data: memories = [], isLoading } = useQuery({
    queryKey: ["memories"],
    queryFn: fetchMemories,
    enabled: isAuthenticated,
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memories"] }),
  });

  const sections = useMemo(() => {
    if (!entityCards) {
      return [{ title: "", data: memories }];
    }
    const byEntity = new Map<string, Memory[]>();
    const ungrouped: Memory[] = [];
    for (const m of memories) {
      const entities = m.entities ?? [];
      if (entities.length === 0) {
        ungrouped.push(m);
        continue;
      }
      for (const e of entities) {
        const list = byEntity.get(e.name) ?? [];
        if (!list.some((x) => x.id === m.id)) list.push(m);
        byEntity.set(e.name, list);
      }
    }
    const out = [...byEntity.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([title, data]) => ({ title, data }));
    if (ungrouped.length) out.push({ title: "Other", data: ungrouped });
    return out.length ? out : [{ title: "", data: [] }];
  }, [memories, entityCards]);

  if (authLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }
  if (!isAuthenticated) return <Redirect href="/login" />;

  const flat = sections.flatMap((s) =>
    s.title
      ? [{ kind: "header" as const, id: `h-${s.title}`, title: s.title }, ...s.data.map((m) => ({ kind: "row" as const, ...m }))]
      : s.data.map((m) => ({ kind: "row" as const, ...m })),
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }} edges={["top"]}>
      <AppBar active="memories" />
      <Text
        style={{
          color: theme.text,
          fontSize: 20,
          fontWeight: "700",
          paddingHorizontal: 18,
          paddingTop: 14,
          paddingBottom: 4,
        }}
      >
        Your memories
      </Text>

      {isLoading ? (
        <ActivityIndicator color={theme.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={flat}
          keyExtractor={(item) => ("kind" in item && item.kind === "header" ? item.id : item.id)}
          contentContainerStyle={{ padding: 16, gap: 10 }}
          ListEmptyComponent={
            <Text style={{ color: theme.textDim, textAlign: "center", marginTop: 60 }}>
              Nothing saved yet. Head to the chat and tell me something to remember.
            </Text>
          }
          renderItem={({ item }) => {
            if (item.kind === "header") {
              return (
                <Text
                  style={{
                    color: theme.accent,
                    fontSize: 13,
                    letterSpacing: 2,
                    fontWeight: "700",
                    marginTop: 8,
                  }}
                >
                  {item.title.toUpperCase()}
                </Text>
              );
            }
            const locked =
              sensitiveLock &&
              (item.sensitivity === "sensitive" ||
                item.sensitivity === "restricted") &&
              !revealed[item.id];
            return (
              <MemoryRow
                memory={item}
                locked={locked}
                onReveal={() => setRevealed((r) => ({ ...r, [item.id]: true }))}
                onDelete={() => remove.mutate(item.id)}
                deleting={remove.isPending && remove.variables === item.id}
              />
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}

function MemoryRow({
  memory,
  locked,
  onReveal,
  onDelete,
  deleting,
}: {
  memory: Memory;
  locked: boolean;
  onReveal: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <View
      style={{
        backgroundColor: theme.surface,
        borderColor: theme.border,
        borderWidth: 1,
        borderRadius: 14,
        padding: 15,
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
      }}
    >
      <Pressable style={{ flex: 1 }} onPress={locked ? onReveal : undefined}>
        <Text
          style={{
            color: theme.text,
            fontSize: 16,
            lineHeight: 22,
            opacity: locked ? 0.35 : 1,
          }}
        >
          {locked ? "•••• Sensitive — tap to reveal" : memory.content}
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 12, marginTop: 6 }}>
          {memory.source} · {new Date(memory.createdAt).toLocaleDateString()}
        </Text>
      </Pressable>
      <Pressable hitSlop={8} onPress={onDelete} disabled={deleting}>
        <Text style={{ color: theme.danger, fontSize: 14 }}>
          {deleting ? "…" : "Delete"}
        </Text>
      </Pressable>
    </View>
  );
}
