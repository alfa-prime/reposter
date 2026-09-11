import { useEffect, useState } from "react";
import { Moon, Settings, Sun, X } from "lucide-react";

type Theme = "dark" | "light";

const STORAGE_KEY = "uncle-vlad-theme";

function initialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const isLight = theme === "light";

  return (
    <div className={`settings-dock ${open ? "open" : ""}`}>
      {open && (
        <div className="settings-popover" role="dialog" aria-label="Настройки интерфейса">
          <div className="settings-popover-head">
            <div>
              <strong>Настройки</strong>
              <span>Интерфейс</span>
            </div>
            <button className="settings-close" type="button" onClick={() => setOpen(false)} aria-label="Закрыть настройки">
              <X size={16} />
            </button>
          </div>

          <div className="settings-row">
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

          <div className="settings-placeholder">Состояние сервисов позже перенесём сюда.</div>
        </div>
      )}

      <button className="settings-trigger" type="button" onClick={() => setOpen((value) => !value)} aria-label="Настройки" aria-expanded={open}>
        <Settings size={17} />
        <span>Настройки</span>
      </button>
    </div>
  );
}
