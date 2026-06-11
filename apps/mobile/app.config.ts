import type { ExpoConfig } from "expo/config";

// Base API URL is read from EXPO_PUBLIC_API_URL at build/start time and exposed
// to the app via expo-constants `extra`. Defaults to the local FastAPI server.
const config: ExpoConfig = {
  name: "MyMemory",
  slug: "mymemory",
  scheme: "mymemory",
  version: "0.1.0",
  orientation: "portrait",
  userInterfaceStyle: "dark",
  newArchEnabled: true,
  ios: {
    supportsTablet: true,
    bundleIdentifier: "com.pborgen.mymemory",
    infoPlist: {
      NSMicrophoneUsageDescription:
        "MyMemory uses the microphone so you can speak the things you want to remember.",
      NSSpeechRecognitionUsageDescription:
        "MyMemory transcribes your speech on-device so you can save and recall memories by voice.",
    },
  },
  android: {
    package: "com.pborgen.mymemory",
  },
  plugins: ["expo-router", "expo-secure-store", "expo-speech-recognition"],
  extra: {
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8080",
  },
};

export default config;
