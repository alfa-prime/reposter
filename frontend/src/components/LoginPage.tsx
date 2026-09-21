import { FormEvent, useEffect, useState } from "react";
import {
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  LogIn,
  Moon,
  RefreshCw,
  Sun,
} from "lucide-react";
import { ApiError } from "../api";
import { useAuth } from "../auth";
import { projectLogo } from "../logoData";
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

function AuthFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className="auth-page">
      <AuthThemeToggle />
      <section className="auth-card">{children}</section>
      <p className="auth-footer">Редакционная система · защищённая сессия</p>
    </main>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await login({ username, password });
    } catch (exc) {
      if (exc instanceof ApiError && exc.status === 429 && exc.retryAfter !== null) {
        const minutes = Math.max(1, Math.ceil(exc.retryAfter / 60));
        setError(`Слишком много попыток входа. Повторите через ${minutes} мин.`);
      } else {
        setError(exc instanceof Error ? exc.message : "Не удалось войти");
      }
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame>
      <div className="auth-brand">
        <div className="auth-brand-logo">
          <img src={projectLogo} alt="Дядя Влад" decoding="async" />
        </div>
        <p className="eyebrow">ДЯДЯ ВЛАД · ЧИТАЕТ НОВОСТИ</p>
        <h1>Вход в редакцию</h1>
        <p className="auth-subtitle">Введите логин и пароль своей учётной записи.</p>
      </div>

      <form className="auth-form" onSubmit={(event) => void submit(event)}>
        <label>
          <span>Логин</span>
          <input
            type="text"
            name="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={256}
            disabled={busy}
            required
            autoFocus
          />
        </label>

        <label>
          <span>Пароль</span>
          <span className="auth-password-field">
            <input
              type={showPassword ? "text" : "password"}
              name="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              maxLength={1024}
              disabled={busy}
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
              title={showPassword ? "Скрыть пароль" : "Показать пароль"}
              tabIndex={-1}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </span>
        </label>

        {error && <div className="auth-error" role="alert">{error}</div>}

        <button className="primary auth-submit" type="submit" disabled={busy}>
          {busy ? <LoaderCircle size={18} className="spin" /> : <LogIn size={18} />}
          {busy ? "Проверяем…" : "Войти"}
        </button>
      </form>

      <div className="auth-security-note">
        <LockKeyhole size={16} />
        <span>Пароль не сохраняется в браузере. Доступ можно отозвать на сервере.</span>
      </div>
    </AuthFrame>
  );
}

export function AuthLoadingPage() {
  return (
    <AuthFrame>
      <div className="auth-state">
        <LoaderCircle size={30} className="spin" />
        <h1>Проверяем сессию</h1>
        <p>Это займёт несколько секунд.</p>
      </div>
    </AuthFrame>
  );
}

export function AuthUnavailablePage() {
  const { error, restore } = useAuth();
  const [busy, setBusy] = useState(false);

  async function retry() {
    setBusy(true);
    try {
      await restore();
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame>
      <div className="auth-state">
        <LockKeyhole size={30} />
        <h1>Сервис временно недоступен</h1>
        <p>{error || "Не удалось проверить пользовательскую сессию."}</p>
        <button className="secondary" type="button" onClick={() => void retry()} disabled={busy}>
          <RefreshCw size={17} className={busy ? "spin" : ""} />
          Повторить
        </button>
      </div>
    </AuthFrame>
  );
}
