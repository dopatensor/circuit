import { useSyncExternalStore } from "react";

// Light / Dark / System. "System" follows prefers-color-scheme; the choice is saved per
// browser. index.html applies the saved choice before the first paint, so there's no
// flash of the wrong theme.
export type ThemeChoice = "system" | "light" | "dark";
const KEY = "circuit.theme";
const listeners = new Set<() => void>();

export function getTheme(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
  const dark =
    choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]:not([media])')?.setAttribute("content", dark ? "#111110" : "#fbfaf8");
}

export function setTheme(choice: ThemeChoice) {
  try {
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    // Storage blocked (private mode): the choice lasts for this page only.
  }
  applyTheme(choice);
  listeners.forEach((l) => l());
}

export function useTheme(): ThemeChoice {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getTheme,
    () => "system",
  );
}
