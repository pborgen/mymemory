import { useCallback, useEffect, useRef, useState } from "react";

// expo-speech-recognition is a native module: present in a dev build
// (`expo run:ios`), absent in Expo Go. Load it lazily so the app still runs in
// Expo Go — the mic just reports itself unavailable there.
declare const require: (name: string) => any;

let Speech: any = null;
try {
  Speech = require("expo-speech-recognition");
} catch {
  Speech = null;
}

const Module = Speech?.ExpoSpeechRecognitionModule ?? null;

/**
 * On-device iOS speech-to-text. Tapping the mic starts recognition; the partial
 * + final transcript is reported via onResult, and the caller decides what to do
 * with the text (here: drop it into the chat input). No audio leaves the device.
 *
 * Returns `available: false` when the native module isn't present (Expo Go).
 */
export function useVoice(onResult: (text: string) => void) {
  const available = !!Module;
  const [listening, setListening] = useState(false);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  useEffect(() => {
    if (!Module) return;
    const subs = [
      Module.addListener("result", (event: any) => {
        const transcript = event.results?.[0]?.transcript ?? "";
        if (transcript) onResultRef.current(transcript);
      }),
      Module.addListener("end", () => setListening(false)),
      Module.addListener("error", () => setListening(false)),
    ];
    return () => subs.forEach((s: any) => s.remove());
  }, []);

  const start = useCallback(async () => {
    if (!Module) return;
    const perm = await Module.requestPermissionsAsync();
    if (!perm.granted) return;
    setListening(true);
    Module.start({ lang: "en-US", interimResults: true, continuous: false });
  }, []);

  const stop = useCallback(() => {
    if (!Module) return;
    Module.stop();
    setListening(false);
  }, []);

  return { available, listening, start, stop };
}
