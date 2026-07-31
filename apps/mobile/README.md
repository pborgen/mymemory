# MyMemory — mobile (Expo / React Native)

The iOS chat app: tell it facts, ask for them back, by text or voice.

## Run on your iPhone (Apple Developer)

Voice (on-device speech) needs native modules — use a **dev build**, not Expo Go.

### 1. One-time Xcode signing

1. Connect the iPhone with a cable; unlock it and tap **Trust**.
2. On the phone: **Settings → Privacy & Security → Developer Mode** → On (reboot if asked).
3. In Xcode (workspace: `apps/mobile/ios/MyMemory.xcworkspace`):
   - **Xcode → Settings → Accounts** → **+** → sign in with your Apple Developer Apple ID.
   - Select the **MyMemory** target → **Signing & Capabilities**.
   - Check **Automatically manage signing**.
   - Choose your **Team** (Personal Team / paid developer team).
4. If Xcode shows a bundle-id conflict, keep `com.pborgen.mymemory` or change it under your team.

### 2. API reachable from the phone

`localhost` on the phone is the phone itself. Point the app at your Mac’s LAN IP
and bind the API to all interfaces:

```bash
# Mac — API (all interfaces)
cd apps/api && uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8080
```

Phone and Mac must be on the same Wi‑Fi (or Tailscale).

### 3. Build & install

```bash
cd apps/mobile
EXPO_PUBLIC_API_URL=http://192.168.68.104:8080 npx expo run:ios --device
```

Replace the IP with yours (`ipconfig getifaddr en0`). First build takes a few minutes.

### Simulator (no cable)

```bash
EXPO_PUBLIC_API_URL=http://localhost:8080 npx expo run:ios
```

## Structure

- `app/_layout.tsx` — providers (React Query, Auth) + Stack navigator.
- `app/index.tsx` — redirects to `/chat` or `/login` based on auth.
- `app/login.tsx` — dev account sign-in (and a hook for Google OAuth).
- `app/chat.tsx` — the store-or-recall chat, with text input + mic button.
- `app/memories.tsx` — list / delete saved memories.
- `src/api.ts` — `apiFetch` wrapper + memory endpoints; auth in `expo-secure-store`.
- `src/auth.tsx` — auth React context.
- `src/useVoice.ts` — on-device iOS speech-to-text → fills the chat input.
- `src/theme.ts` — warm amber-on-dark palette.

Config (`app.config.ts`) reads `EXPO_PUBLIC_API_URL` and declares the
microphone + speech-recognition usage strings required on iOS.
