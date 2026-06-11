# MyMemory — mobile (Expo / React Native)

The iOS chat app: tell it facts, ask for them back, by text or voice.

## Run

Voice (on-device speech) and Google sign-in need native modules, so use an
**Expo dev build**, not Expo Go.

```bash
npm install
# Point at your running FastAPI backend:
EXPO_PUBLIC_API_URL=http://localhost:8080 npx expo start

# First time on a simulator/device (builds the native dev client):
npx expo run:ios
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
