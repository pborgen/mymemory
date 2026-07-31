import type { ExpoConfig } from "expo/config";

// Base API URL is read from EXPO_PUBLIC_API_URL at build/start time and exposed
// to the app via expo-constants `extra`. Defaults to the local FastAPI server.
const googleIosClientId = (
  process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? ""
).trim();
const googleIosUrlScheme = googleIosClientId
  ? `com.googleusercontent.apps.${googleIosClientId.replace(
      /\.apps\.googleusercontent\.com$/i,
      "",
    )}`
  : undefined;

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
      // Phone → Mac LAN API over http:// (dev). Required once ATS is on.
      NSAppTransportSecurity: {
        NSAllowsLocalNetworking: true,
      },
      ...(googleIosUrlScheme
        ? {
            CFBundleURLTypes: [
              {
                CFBundleURLSchemes: ["mymemory", googleIosUrlScheme],
              },
            ],
          }
        : {}),
    },
  },
  android: {
    package: "com.pborgen.mymemory",
  },
  plugins: [
    "expo-router",
    "expo-secure-store",
    "expo-speech-recognition",
    "expo-web-browser",
  ],
  extra: {
    // Point at AWS App Runner for Google prod login, e.g.:
    // EXPO_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com
    apiUrl: process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8080",
  },
};

export default config;
