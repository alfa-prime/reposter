import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "dark" | "light";

const STORAGE_KEY = "uncle-vlad-theme";

function initialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const isLight = theme === "light";

  return (
    <button
      className="theme-switch"
      type="button"
      onClick={() => setTheme(isLight ? "dark" : "light")}
      title={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
      aria-label={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
      aria-pressed={isLight}
    >
      <span className="theme-switch-label">Тема</span>
      <span className="theme-switch-track" aria-hidden="true">
        <Sun size={13} className="theme-switch-sun" />
        <Moon size={13} className="theme-switch-moon" />
        <span className="theme-switch-thumb" />
      </span>
    </button>
  );
}
