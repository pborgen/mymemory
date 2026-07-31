# MyMemory — mobile (Expo / React Native)

The iOS chat app: tell it facts, ask them back, by text or voice.

## Run on Simulator (quick start)

Local API must be running with dev auth:

```bash
# Terminal 1 — from repo root
npm run db:up
cd apps/api && uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8080

# Terminal 2
cd apps/mobile
EXPO_PUBLIC_API_URL=http://127.0.0.1:8080 npx expo run:ios
```

Sign in as **Paul** or **Alex** on the login screen.

### Xcode 26 note

Apple Clang breaks the vendored `fmt` 11 pod (consteval errors). The
`ios/Podfile` forces the `fmt` target to C++17. If you regenerate native
projects (`npx expo prebuild --clean`), re-apply that `post_install` block
(or upgrade to RN 0.84+ / Expo that ships fmt 12.1).

## Run on your iPhone (Apple Developer)

Voice (on-device speech) needs native modules — use a **dev build**, not Expo Go.

Your phone must show up online:

```bash
xcrun xctrace list devices
```

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

`localhost` on the phone is the phone itself. Point the app at your Mac’s LAN IP:

```bash
cd apps/api && uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8080
```

Phone and Mac must be on the same Wi‑Fi (or Tailscale).

### 3. Build & install

```bash
cd apps/mobile
EXPO_PUBLIC_API_URL=http://$(ipconfig getifaddr en0):8080 npx expo run:ios --device
```

First build takes a few minutes. After install, tap **Paul** / **Alex** to sign in.

## Structure

- `app/_layout.tsx` — providers (React Query, Auth) + Stack navigator.
- `app/index.tsx` — redirects to `/chat` or `/login` based on auth.
- `app/login.tsx` — Google sign-in + optional Paul/Alex when API has dev auth.
- `app/chat.tsx` — the store-or-recall chat, with text input + mic button.
- `app/memories.tsx` — list / delete saved memories.
- `src/GoogleSignIn.tsx` — expo-auth-session Google ID-token flow.
- `src/api.ts` — `apiFetch` wrapper + memory/auth endpoints; auth in `expo-secure-store`.
- `src/auth.tsx` — auth React context.
- `src/useVoice.ts` — on-device iOS speech-to-text → fills the chat input.
- `src/theme.ts` — warm amber-on-dark palette.

## Google sign-in against AWS

1. Create an **iOS** OAuth client (bundle `com.pborgen.mymemory`) — see
   [`infra/GOOGLE_AUTH.md`](../../infra/GOOGLE_AUTH.md).
2. Set `google_ios_client_id` in Terraform and apply (API accepts web + iOS audiences).
3. Rebuild pointing at App Runner:

```bash
cd apps/mobile
EXPO_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com \
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=YOUR_IOS_ID.apps.googleusercontent.com \
  npx expo run:ios
```

Local Mac with empty `GOOGLE_CLIENT_ID` keeps Paul/Alex only.

Config (`app.config.ts`) reads `EXPO_PUBLIC_API_URL` and declares the
microphone + speech-recognition usage strings required on iOS.
