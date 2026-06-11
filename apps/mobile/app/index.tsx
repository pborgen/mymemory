import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "@/auth";
import { theme } from "@/theme";

// Entry point: bounce to the chat or the login screen based on auth state.
export default function Index() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }

  return <Redirect href={isAuthenticated ? "/chat" : "/login"} />;
}
