"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Minimal Web Speech API surface (Chrome / Safari / Edge). */
interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly 0: { transcript: string };
}

interface SpeechRecognitionEventLike {
  readonly resultIndex: number;
  readonly results: ArrayLike<SpeechRecognitionResultLike> & {
    length: number;
  };
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/**
 * Browser speech-to-text into the chat composer.
 * Uses the Web Speech API (Chrome, Edge, Safari). Audio is handled by the
 * browser / OS — nothing is uploaded to our API.
 */
export function useVoice(onResult: (text: string) => void) {
  const [available, setAvailable] = useState(false);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;
  // Keep the last final chunks so interim updates don't wipe earlier phrases.
  const finalsRef = useRef("");

  useEffect(() => {
    setAvailable(!!getSpeechRecognitionCtor());
  }, []);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, []);

  const stop = useCallback(() => {
    const rec = recognitionRef.current;
    if (rec) {
      rec.onend = null;
      rec.stop();
      recognitionRef.current = null;
    }
    setListening(false);
  }, []);

  const start = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    // Restart cleanly if already listening.
    recognitionRef.current?.abort();
    finalsRef.current = "";

    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";

    rec.onresult = (event) => {
      let interim = "";
      let finals = finalsRef.current;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0]?.transcript ?? "";
        if (event.results[i].isFinal) {
          finals = `${finals}${piece} `.replace(/\s+/g, " ");
        } else {
          interim += piece;
        }
      }
      finalsRef.current = finals;
      const text = `${finals}${interim}`.trim();
      if (text) onResultRef.current(text);
    };

    rec.onerror = () => {
      recognitionRef.current = null;
      setListening(false);
    };

    rec.onend = () => {
      // Browser may end the session after a pause; keep UI in sync.
      if (recognitionRef.current === rec) {
        recognitionRef.current = null;
        setListening(false);
      }
    };

    try {
      rec.start();
      recognitionRef.current = rec;
      setListening(true);
    } catch {
      setListening(false);
    }
  }, []);

  const toggle = useCallback(() => {
    if (listening) stop();
    else start();
  }, [listening, start, stop]);

  return { available, listening, start, stop, toggle };
}
