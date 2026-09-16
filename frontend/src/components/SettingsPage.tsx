import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { applyTheme, getInitialTheme, Theme } from "../theme";

export function SettingsPage() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const isLight = theme === "light";

  return (
    <section className="settings-page">
      <header className="settings-page-head">
        <p className="eyebrow">ДЯДЯ ВЛАД · ЧИТАЕТ НОВОСТИ</p>
        <h1>Настройки</h1>
      </header>

      <div className="settings-page-card">
        <div className="settings-row-copy">
          <strong>Оформление</strong>
          <span>{isLight ? "Светлая тема" : "Тёмная тема"}</span>
        </div>

        <button
          className="theme-switch"
          type="button"
          onClick={() => setTheme(isLight ? "dark" : "light")}
          aria-label={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
          aria-pressed={isLight}
        >
          <span className="theme-switch-track" aria-hidden="true">
            <Sun size={13} className="theme-switch-sun" />
            <Moon size={13} className="theme-switch-moon" />
            <span className="theme-switch-thumb" />
          </span>
        </button>
      </div>
    </section>
  );
}
