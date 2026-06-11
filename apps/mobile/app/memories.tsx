import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Redirect } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { deleteMemory, fetchMemories } from "@/api";
import { useAuth } from "@/auth";
import { theme } from "@/theme";
import type { Memory } from "@/types";

export default function Memories() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const { data: memories = [], isLoading } = useQuery({
    queryKey: ["memories"],
    queryFn: fetchMemories,
    enabled: isAuthenticated,
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memories"] }),
  });

  if (authLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }
  if (!isAuthenticated) return <Redirect href="/login" />;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }} edges={["top"]}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          paddingHorizontal: 18,
          paddingBottom: 12,
          borderBottomColor: theme.border,
          borderBottomWidth: 1,
        }}
      >
        <Text style={{ color: theme.text, fontSize: 20, fontWeight: "700" }}>
          Your memories
        </Text>
        <Link href="/chat" asChild>
          <Pressable hitSlop={8}>
            <Text style={{ color: theme.accent, fontSize: 15 }}>Chat ›</Text>
          </Pressable>
        </Link>
      </View>

      {isLoading ? (
        <ActivityIndicator color={theme.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={memories}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 16, gap: 10 }}
          ListEmptyComponent={
            <Text style={{ color: theme.textDim, textAlign: "center", marginTop: 60 }}>
              Nothing saved yet. Head to the chat and tell me something to remember.
            </Text>
          }
          renderItem={({ item }) => (
            <MemoryRow
              memory={item}
              onDelete={() => remove.mutate(item.id)}
              deleting={remove.isPending && remove.variables === item.id}
            />
          )}
        />
      )}
    </SafeAreaView>
  );
}

function MemoryRow({
  memory,
  onDelete,
  deleting,
}: {
  memory: Memory;
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
      <View style={{ flex: 1 }}>
        <Text style={{ color: theme.text, fontSize: 16, lineHeight: 22 }}>
          {memory.content}
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 12, marginTop: 6 }}>
          {memory.source} · {new Date(memory.createdAt).toLocaleDateString()}
        </Text>
      </View>
      <Pressable hitSlop={8} onPress={onDelete} disabled={deleting}>
        <Text style={{ color: theme.danger, fontSize: 14 }}>
          {deleting ? "…" : "Delete"}
        </Text>
      </Pressable>
    </View>
  );
}
