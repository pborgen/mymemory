"use client";

import { useEffect, useState } from "react";

// Switchable UI themes. "mint" is the default :root palette; the others are
// [data-theme] overrides in globals.css. Persisted in localStorage and applied
// pre-paint by the inline script in app/layout.tsx.
export const THEME_KEY = "mymemory_theme";

export const THEMES = [
  { id: "mint", label: "Mint", swatch: "#9aff6b" },
  { id: "volt", label: "Volt", swatch: "#c6ff3d" },
  { id: "grape", label: "Grape", swatch: "#a78bfa" },
  { id: "sticker", label: "Sticker", swatch: "#ff6b4a" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

function loadTheme(): ThemeId {
  if (typeof window === "undefined") return "mint";
  const saved = window.localStorage.getItem(THEME_KEY);
  return THEMES.some((t) => t.id === saved) ? (saved as ThemeId) : "mint";
}

export function applyTheme(id: ThemeId): void {
  if (id === "mint") {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = id;
  }
  window.localStorage.setItem(THEME_KEY, id);
}

export function ThemePicker() {
  // Render a stable default on the server, then sync to the saved theme.
  const [theme, setTheme] = useState<ThemeId>("mint");
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
