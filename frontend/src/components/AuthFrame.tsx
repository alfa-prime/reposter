import { Moon, Sun } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { applyTheme, getInitialTheme, Theme } from "../theme";

function AuthThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const isLight = theme === "light";

  useEffect(() => applyTheme(theme), [theme]);

  return (
    <button
      className="auth-theme-toggle"
      type="button"
      onClick={() => setTheme(isLight ? "dark" : "light")}
      aria-label={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
      title={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
    >
      {isLight ? <Moon size={18} /> : <Sun size={18} />}
    </button>
  );
}

export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="auth-page">
      <AuthThemeToggle />
      <section className="auth-card">{children}</section>
      <p className="auth-footer">Редакционная система · защищённая сессия</p>
    </main>
  );
}
