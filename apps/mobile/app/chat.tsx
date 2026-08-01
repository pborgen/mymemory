import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Redirect } from "expo-router";
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

import { fetchSettings, sendMemoryChat } from "@/api";
import { AppBar } from "@/AppBar";
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
  const { isAuthenticated, isLoading } = useAuth();
  const queryClient = useQueryClient();
  const sessionId = useRef<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const listRef = useRef<FlatList<ChatMessage>>(null);

  const { available: voiceAvailable, listening, start, stop } = useVoice((text) =>
    setInput(text),
  );

  const { data: settingsData } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: isAuthenticated,
  });
  const showSources = !!settingsData?.settings.showSources;

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
          chips: res.chips,
        },
      ]);
      if (
        res.action === "stored" ||
        res.action === "forgotten" ||
        res.action === "updated"
      ) {
        queryClient.invalidateQueries({ queryKey: ["memories"] });
      }
      if (res.action === "reminded") {
        queryClient.invalidateQueries({ queryKey: ["reminders"] });
      }
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: `⚠️ ${err.message}` },
      ]);
    },
  });

  const sendText = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || mutation.isPending) return;
      if (listening) stop();
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content: trimmed },
      ]);
      setInput("");
      mutation.mutate(trimmed);
    },
    [mutation, listening, stop],
  );

  const send = useCallback(() => sendText(input), [input, sendText]);

  const onChip = useCallback(
    (chipId: string) => {
      if (chipId === "undo") sendText("Forget the last memory you stored");
      else if (chipId === "ask") setInput("What do you remember about ");
    },
    [sendText],
  );

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
      <AppBar active="chat" />

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
          renderItem={({ item }) => (
            <Bubble message={item} showSources={showSources} onChip={onChip} />
          )}
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
          {voiceAvailable ? (
            <Pressable
              onPress={listening ? stop : start}
              accessibilityRole="button"
              accessibilityLabel={listening ? "Stop listening" : "Speak into chat"}
              accessibilityState={{ selected: listening }}
              style={{
                width: 46,
                height: 46,
                borderRadius: 23,
                backgroundColor: listening ? theme.accent : theme.surface,
                borderColor: listening ? theme.accent : theme.border,
                borderWidth: 1,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text
                style={{
                  fontSize: 11,
                  fontWeight: "700",
                  letterSpacing: 0.5,
                  color: listening ? theme.bg : theme.text,
                }}
              >
                {listening ? "STOP" : "MIC"}
              </Text>
            </Pressable>
          ) : null}

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

function Bubble({
  message,
  showSources,
  onChip,
}: {
  message: ChatMessage;
  showSources: boolean;
  onChip: (id: string) => void;
}) {
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
        {message.action === "stored" ? (
          <Text style={{ color: theme.accent, fontSize: 11, letterSpacing: 1, marginBottom: 4 }}>
            {"✓ SAVED"}
          </Text>
        ) : null}
        {message.action === "forgotten" ? (
          <Text style={{ color: theme.danger, fontSize: 11, letterSpacing: 1, marginBottom: 4 }}>
            {"✕ FORGOTTEN"}
          </Text>
        ) : null}
        {message.action === "updated" ? (
          <Text style={{ color: theme.accent, fontSize: 11, letterSpacing: 1, marginBottom: 4 }}>
            {"✎ UPDATED"}
          </Text>
        ) : null}
        <Text
          style={{
            color: isUser ? theme.userText : theme.text,
            fontSize: 16,
            lineHeight: 22,
          }}
        >
          {message.content}
        </Text>
        {showSources && message.sources && message.sources.length > 0 ? (
          <View style={{ marginTop: 8, paddingTop: 8, borderTopColor: theme.border, borderTopWidth: 1 }}>
            <Text style={{ color: theme.textDim, fontSize: 11, marginBottom: 4 }}>
              Why this answer
            </Text>
            {message.sources.map((s) => (
              <Text key={s.id} style={{ color: theme.textDim, fontSize: 12, lineHeight: 17 }}>
                • {s.content}
              </Text>
            ))}
          </View>
        ) : null}
        {message.chips && message.chips.length > 0 ? (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
            {message.chips.map((c) => (
              <Pressable
                key={c.id}
                onPress={() => onChip(c.id)}
                style={{
                  borderColor: theme.border,
                  borderWidth: 1,
                  borderRadius: 999,
                  paddingVertical: 6,
                  paddingHorizontal: 12,
                  backgroundColor: theme.surfaceAlt,
                }}
              >
                <Text style={{ color: theme.text, fontSize: 13 }}>{c.label}</Text>
              </Pressable>
            ))}
          </View>
        ) : null}
      </View>
    </View>
  );
}
