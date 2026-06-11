import { useQuery } from "@tanstack/react-query";
import { Redirect } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { fetchDevAccounts } from "@/api";
import { useAuth } from "@/auth";
import { theme } from "@/theme";

export default function Login() {
  const { isAuthenticated, isLoading, signInDev } = useAuth();
  const { data: devAccounts = [] } = useQuery({
    queryKey: ["devAccounts"],
    queryFn: fetchDevAccounts,
  });

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg, justifyContent: "center" }}>
        <ActivityIndicator color={theme.accent} />
      </View>
    );
  }
  if (isAuthenticated) return <Redirect href="/chat" />;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.bg }}>
      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: 28 }}>
        <Text style={{ color: theme.accent, fontSize: 13, letterSpacing: 4, marginBottom: 8 }}>
          MYMEMORY
        </Text>
        <Text style={{ color: theme.text, fontSize: 34, fontWeight: "700", lineHeight: 40 }}>
          Tell it once.{"\n"}Ask it anytime.
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 16, marginTop: 16, lineHeight: 23 }}>
          Say or type anything you want to remember — a license plate, a friend's
          address, a Wi-Fi password — then just ask for it later.
        </Text>

        <View style={{ marginTop: 40 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>
            DEV SIGN-IN
          </Text>
          {devAccounts.length === 0 ? (
            <Text style={{ color: theme.textDim }}>
              No dev accounts. Start the API with ALLOW_DEV_AUTH_HEADERS=true.
            </Text>
          ) : (
            devAccounts.map((acct) => (
              <Pressable
                key={acct.email}
                onPress={() => signInDev(acct.email)}
                style={({ pressed }) => ({
                  backgroundColor: pressed ? theme.surfaceAlt : theme.surface,
                  borderColor: theme.border,
                  borderWidth: 1,
                  borderRadius: 14,
                  paddingVertical: 16,
                  paddingHorizontal: 18,
                  marginBottom: 10,
                })}
              >
                <Text style={{ color: theme.text, fontSize: 16, fontWeight: "600" }}>
                  {acct.name}
                </Text>
                <Text style={{ color: theme.textDim, fontSize: 13, marginTop: 2 }}>
                  {acct.email}
                </Text>
              </Pressable>
            ))
          )}
        </View>

        <Text style={{ color: theme.textDim, fontSize: 12, marginTop: 28, lineHeight: 18 }}>
          Google sign-in is wired on the backend (POST /api/auth/google). Add an
          expo-auth-session Google flow here to enable production login.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
