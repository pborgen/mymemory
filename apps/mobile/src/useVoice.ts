import { useCallback, useEffect, useRef, useState } from "react";
import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from "expo-speech-recognition";

/**
 * On-device iOS speech-to-text. Tapping the mic starts recognition; the partial
 * + final transcript is reported via onResult, and the caller decides what to do
 * with the text (here: drop it into the chat input). No audio leaves the device.
 */
export function useVoice(onResult: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const latest = useRef("");

  useSpeechRecognitionEvent("result", (event) => {
    const transcript = event.results?.[0]?.transcript ?? "";
    if (transcript) {
      latest.current = transcript;
      onResult(transcript);
    }
  });

  useSpeechRecognitionEvent("end", () => setListening(false));
  useSpeechRecognitionEvent("error", () => setListening(false));

  const start = useCallback(async () => {
    const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!perm.granted) return;
    latest.current = "";
    setListening(true);
    ExpoSpeechRecognitionModule.start({
      lang: "en-US",
      interimResults: true,
      continuous: false,
    });
  }, []);

  const stop = useCallback(() => {
    ExpoSpeechRecognitionModule.stop();
    setListening(false);
  }, []);

  useEffect(() => () => ExpoSpeechRecognitionModule.abort(), []);

  return { listening, start, stop };
}
