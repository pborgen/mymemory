"use client";

import { useEffect, useState } from "react";

// Switchable UI themes. "lumen" is the default :root palette; the others are
// [data-theme] overrides in globals.css. Persisted in localStorage and applied
// pre-paint by the inline script in app/layout.tsx.
export const THEME_KEY = "mymemory_theme";

export const THEMES = [
  { id: "lumen", label: "Lumen", swatch: "#0f8f86" },
  { id: "night", label: "Night", swatch: "#9aff6b" },
  { id: "volt", label: "Volt", swatch: "#c6ff3d" },
  { id: "grape", label: "Grape", swatch: "#a78bfa" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

function normalizeTheme(raw: string | null): ThemeId {
  // Migrate the old default id so saved prefs still resolve.
  if (raw === "mint" || raw === "sticker") return "lumen";
  return THEMES.some((t) => t.id === raw) ? (raw as ThemeId) : "lumen";
}

function loadTheme(): ThemeId {
  if (typeof window === "undefined") return "lumen";
  return normalizeTheme(window.localStorage.getItem(THEME_KEY));
}

export function applyTheme(id: ThemeId): void {
  if (id === "lumen") {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = id;
  }
  window.localStorage.setItem(THEME_KEY, id);
}

export function ThemePicker() {
  // Render a stable default on the server, then sync to the saved theme.
  const [theme, setTheme] = useState<ThemeId>("lumen");
  useEffect(() => setTheme(loadTheme()), []);

  const pick = (id: ThemeId) => {
    setTheme(id);
    applyTheme(id);
  };

  return (
    <span className="theme-picker" role="group" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`theme-dot${theme === t.id ? " active" : ""}`}
          style={{ background: t.swatch }}
          title={t.label}
          aria-label={`${t.label} theme`}
          onClick={() => pick(t.id)}
        />
      ))}
    </span>
  );
}
