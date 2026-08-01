import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { useAuth } from "@/auth";
import { theme } from "@/theme";

type AppBarActive = "chat" | "memories" | "settings" | "prompts";

function NavLink({
  href,
  label,
  active,
}: {
  href: "/chat" | "/memories" | "/settings" | "/prompts";
  label: string;
  active: boolean;
}) {
  return (
    <Link href={href} asChild>
      <Pressable hitSlop={8}>
        <Text
          style={{
            color: active ? theme.accent : theme.textDim,
            fontSize: 14,
            fontWeight: active ? "700" : "500",
          }}
        >
          {label}
        </Text>
      </Pressable>
    </Link>
  );
}

/** Shared top bar: Chat · Memories | Settings | Sign out — mirrors web AppBar. */
export function AppBar({ active }: { active: AppBarActive }) {
  const { signOut } = useAuth();

  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        paddingHorizontal: 18,
        paddingBottom: 12,
        borderBottomColor: theme.border,
        borderBottomWidth: 1,
      }}
    >
      <Text
        style={{
          color: theme.accent,
          fontSize: 12,
          letterSpacing: 2.5,
          fontWeight: "800",
        }}
      >
        MYMEMORY
      </Text>

      <View style={{ flexDirection: "row", alignItems: "center", gap: 14, flexShrink: 1 }}>
        <NavLink href="/chat" label="Chat" active={active === "chat"} />
        <NavLink href="/memories" label="Memories" active={active === "memories"} />
        <View
          style={{
            width: 1,
            height: 14,
            backgroundColor: theme.border,
          }}
        />
        <NavLink href="/settings" label="Settings" active={active === "settings"} />
        <Pressable hitSlop={8} onPress={() => signOut()}>
          <Text style={{ color: theme.textDim, fontSize: 14 }}>Sign out</Text>
        </Pressable>
      </View>
    </View>
  );
}
