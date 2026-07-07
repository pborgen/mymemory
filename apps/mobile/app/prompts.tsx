import { useQuery } from "@tanstack/react-query";
import { Link, Redirect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { fetchPrompts } from "@/api";
import { useAuth } from "@/auth";
import { theme } from "@/theme";
import type { Prompt } from "@/types";

export default function Prompts() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: fetchPrompts,
    enabled: isAuthenticated,
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
          Prompts
        </Text>
        <Link href="/memories" asChild>
          <Pressable hitSlop={8}>
            <Text style={{ color: theme.accent, fontSize: 15 }}>Memories ›</Text>
          </Pressable>
        </Link>
      </View>

      {isLoading ? (
        <ActivityIndicator color={theme.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={prompts}
          keyExtractor={(p) => p.key}
          contentContainerStyle={{ padding: 16, gap: 10 }}
          renderItem={({ item }) => (
            <PromptRow prompt={item} onPress={() => router.push(`/prompt/${item.key}`)} />
          )}
        />
      )}
    </SafeAreaView>
  );
}

function PromptRow({ prompt, onPress }: { prompt: Prompt; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      style={{
        backgroundColor: theme.surface,
        borderColor: theme.border,
        borderWidth: 1,
        borderRadius: 14,
        padding: 15,
      }}
    >
      <Text style={{ color: theme.text, fontSize: 16, fontWeight: "600" }}>
        {prompt.name}
      </Text>
      <Text style={{ color: theme.textDim, fontSize: 13, marginTop: 4, lineHeight: 18 }}>
        {prompt.description}
      </Text>
      <Text style={{ color: theme.textDim, fontSize: 11, marginTop: 6, opacity: 0.8 }}>
        {prompt.key} · v{prompt.activeVersion ?? "—"}
        {prompt.variables.length > 0 && ` · vars: ${prompt.variables.join(", ")}`}
      </Text>
    </Pressable>
  );
}
