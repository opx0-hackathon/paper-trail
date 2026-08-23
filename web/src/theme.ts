export type Theme = "light" | "dark";

const KEY = "pt-theme";

export function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function remember(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    return;
  }
}

export function system(): Theme {
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}
