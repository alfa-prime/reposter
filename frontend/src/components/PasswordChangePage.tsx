import { Eye, EyeOff, LoaderCircle, LockKeyhole, LogOut, Save } from "lucide-react";
import { FormEvent, useState } from "react";
import { useAuth } from "../auth";
import { projectLogo } from "../logoData";
import { AuthFrame } from "./AuthFrame";

export function PasswordChangePage() {
  const { user, changePassword, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPasswords, setShowNewPasswords] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;

    if (newPassword.length < 15) {
      setError("Новый пароль должен содержать не менее 15 символов.");
      return;
    }
    if (newPassword === currentPassword) {
      setError("Новый пароль должен отличаться от текущего.");
      return;
    }
    if (newPassword !== confirmation) {
      setError("Новый пароль и подтверждение не совпадают.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось изменить пароль");
      setCurrentPassword("");
    } finally {
      setBusy(false);
    }
  }

  async function leave() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await logout();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось завершить сессию");
      setBusy(false);
    }
  }

  return (
    <AuthFrame>
      <div className="auth-brand">
        <div className="auth-brand-logo">
          <img src={projectLogo} alt="Дядя Влад" decoding="async" />
        </div>
        <p className="eyebrow">БЕЗОПАСНОСТЬ УЧЁТНОЙ ЗАПИСИ</p>
        <h1>Смените временный пароль</h1>
        <p className="auth-subtitle">
          Для продолжения работы задайте собственный пароль.
        </p>
        {user && (
          <p className="auth-account">
            {user.display_name} <span>@{user.username}</span>
          </p>
        )}
      </div>

      <form className="auth-form" onSubmit={(event) => void submit(event)}>
        <label>
          <span>Текущий временный пароль</span>
          <span className="auth-password-field">
            <input
              type={showCurrentPassword ? "text" : "password"}
              name="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              maxLength={1024}
              disabled={busy}
              required
              autoFocus
            />
            <button
              type="button"
              onClick={() => setShowCurrentPassword((value) => !value)}
              aria-label={showCurrentPassword ? "Скрыть пароль" : "Показать пароль"}
              title={showCurrentPassword ? "Скрыть пароль" : "Показать пароль"}
              tabIndex={-1}
            >
              {showCurrentPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </span>
        </label>

        <label>
          <span>Новый пароль</span>
          <span className="auth-password-field">
            <input
              type={showNewPasswords ? "text" : "password"}
              name="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={15}
              maxLength={1024}
              disabled={busy}
              required
            />
            <button
              type="button"
              onClick={() => setShowNewPasswords((value) => !value)}
              aria-label={showNewPasswords ? "Скрыть новые пароли" : "Показать новые пароли"}
              title={showNewPasswords ? "Скрыть новые пароли" : "Показать новые пароли"}
              tabIndex={-1}
            >
              {showNewPasswords ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </span>
          <small className="auth-field-hint">Не менее 15 символов</small>
        </label>

        <label>
          <span>Повторите новый пароль</span>
          <input
            type={showNewPasswords ? "text" : "password"}
            name="new-password-confirmation"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="new-password"
            minLength={15}
            maxLength={1024}
            disabled={busy}
            required
          />
        </label>

        {error && <div className="auth-error" role="alert">{error}</div>}

        <button className="primary auth-submit" type="submit" disabled={busy}>
          {busy ? <LoaderCircle size={18} className="spin" /> : <Save size={18} />}
          {busy ? "Сохраняем…" : "Сменить пароль"}
        </button>
      </form>

      <div className="auth-security-note">
        <LockKeyhole size={16} />
        <span>После смены пароля остальные активные сессии будут завершены.</span>
      </div>

      <button
        className="auth-logout"
        type="button"
        onClick={() => void leave()}
        disabled={busy}
      >
        <LogOut size={15} />
        Выйти и сменить пользователя
      </button>
    </AuthFrame>
  );
}
