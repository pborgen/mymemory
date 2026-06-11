import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, Redirect } from "expo-router";
import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { sendMemoryChat } from "@/api";
import { useAuth } from "@/auth";
import { theme } from "@/theme";
import type { ChatMessage } from "@/types";
import { useVoice } from "@/useVoice";

let idSeq = 0;
const nextId = () => `m${idSeq++}`;

const GREETING: ChatMessage = {
  id: "greeting",
  role: "assistant",
  content:
    "Hi! Tell me anything you want to remember — like “my car license plate is 8XYZ123” — and ask me for it whenever you need it.",
};

export default function Chat() {
  const { isAuthenticated, isLoading, signOut } = useAuth();
  const queryClient = useQueryClient();
  const sessionId = useRef<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const listRef = useRef<FlatList<ChatMessage>>(null);

  const { listening, start, stop } = useVoice((text) => setInput(text));

  const mutation = useMutation({
    mutationFn: (message: string) => sendMemoryChat(message, sessionId.current),
    onSuccess: (res) => {
      sessionId.current = res.sessionId;
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: res.answer,
          action: res.action,
          sources: res.sources,
        },
      ]);
      if (res.action === "stored") {
        queryClient.invalidateQueries({ queryKey: ["memories"] });
      }
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: `⚠️ ${err.message}` },
      ]);
    },
  });

  const send = useCallback(() => {
    const text = input.trim();
    if (!text || mutation.isPending) return;
    if (listening) stop();
    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: text }]);
    setInput("");
    mutation.mutate(text);
  }, [input, mutation, listening, stop]);

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }
  if (!isAuthenticated) return <Redirect href="/login" />;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }} edges={["top"]}>
      {/* Header */}
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
        <Text style={{ color: theme.accent, fontSize: 13, letterSpacing: 3, fontWeight: "700" }}>
          MYMEMORY
        </Text>
        <View style={{ flexDirection: "row", gap: 18 }}>
          <Link href="/memories" asChild>
            <Pressable hitSlop={8}>
              <Text style={{ color: theme.textDim, fontSize: 14 }}>Memories</Text>
            </Pressable>
          </Link>
          <Pressable hitSlop={8} onPress={() => signOut()}>
            <Text style={{ color: theme.textDim, fontSize: 14 }}>Sign out</Text>
          </Pressable>
        </View>
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={8}
      >
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 16, gap: 12 }}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          renderItem={({ item }) => <Bubble message={item} />}
        />

        {mutation.isPending && (
          <Text style={{ color: theme.textDim, paddingHorizontal: 20, paddingBottom: 6 }}>
            thinking…
          </Text>
        )}

        {/* Composer */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "flex-end",
            gap: 10,
            paddingHorizontal: 14,
            paddingTop: 8,
            paddingBottom: 12,
            borderTopColor: theme.border,
            borderTopWidth: 1,
          }}
        >
          <Pressable
            onPress={listening ? stop : start}
            style={{
              width: 46,
              height: 46,
              borderRadius: 23,
              backgroundColor: listening ? theme.accent : theme.surface,
              borderColor: theme.border,
              borderWidth: 1,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ fontSize: 20 }}>{listening ? "⏹" : "🎙"}</Text>
          </Pressable>

          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder={listening ? "Listening…" : "Tell me or ask me…"}
            placeholderTextColor={theme.textDim}
            multiline
            style={{
              flex: 1,
              minHeight: 46,
              maxHeight: 120,
              color: theme.text,
              backgroundColor: theme.surface,
              borderColor: theme.border,
              borderWidth: 1,
              borderRadius: 16,
              paddingHorizontal: 16,
              paddingTop: 12,
              paddingBottom: 12,
              fontSize: 16,
            }}
            onSubmitEditing={send}
          />

          <Pressable
            onPress={send}
            disabled={!input.trim() || mutation.isPending}
            style={{
              width: 46,
              height: 46,
              borderRadius: 23,
              backgroundColor: input.trim() ? theme.accent : theme.surface,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ fontSize: 20, color: input.trim() ? theme.bg : theme.textDim }}>
              {"↑"}
            </Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <View style={{ alignItems: isUser ? "flex-end" : "flex-start" }}>
      <View
        style={{
          maxWidth: "86%",
          backgroundColor: isUser ? theme.user : theme.surface,
          borderColor: isUser ? "transparent" : theme.border,
          borderWidth: isUser ? 0 : 1,
          borderRadius: 18,
          borderBottomRightRadius: isUser ? 4 : 18,
          borderBottomLeftRadius: isUser ? 18 : 4,
          paddingVertical: 11,
          paddingHorizontal: 15,
        }}
      >
        {message.action === "stored" && (
          <Text style={{ color: theme.accent, fontSize: 11, letterSpacing: 1, marginBottom: 4 }}>
            {"✓ SAVED"}
          </Text>
        )}
        <Text
          style={{
            color: isUser ? theme.userText : theme.text,
            fontSize: 16,
            lineHeight: 22,
          }}
        >
          {message.content}
        </Text>
      </View>
    </View>
  );
}
