import { Eye, EyeOff, KeyRound, LoaderCircle, Save, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { useAuth } from "../auth";

type Props = {
  onClose: () => void;
  onChanged: () => void;
};

export function ChangePasswordModal({ onClose, onChanged }: Props) {
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPasswords, setShowPasswords] = useState(false);
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
      onChanged();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось изменить пароль");
      setCurrentPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={() => !busy && onClose()}>
      <div className="modal-card password-change-modal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">БЕЗОПАСНОСТЬ УЧЁТНОЙ ЗАПИСИ</p>
            <h2>Сменить пароль</h2>
          </div>
          <button className="icon-button" type="button" aria-label="Закрыть" onClick={onClose} disabled={busy}>
            <X size={18} />
          </button>
        </div>

        <p className="password-change-copy">Введите текущий пароль и задайте новый. После сохранения остальные активные сессии будут завершены.</p>

        <form className="auth-form password-change-form" onSubmit={(event) => void submit(event)}>
          <label>
            <span>Текущий пароль</span>
            <span className="auth-password-field">
              <input
                type={showPasswords ? "text" : "password"}
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                autoComplete="current-password"
                maxLength={1024}
                disabled={busy}
                required
                autoFocus
              />
              <button type="button" tabIndex={-1} title={showPasswords ? "Скрыть пароли" : "Показать пароли"} aria-label={showPasswords ? "Скрыть пароли" : "Показать пароли"} onClick={() => setShowPasswords((value) => !value)}>
                {showPasswords ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </span>
          </label>

          <label>
            <span>Новый пароль</span>
            <input
              type={showPasswords ? "text" : "password"}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={15}
              maxLength={1024}
              disabled={busy}
              required
            />
            <small className="auth-field-hint">Не менее 15 символов</small>
          </label>

          <label>
            <span>Повторите новый пароль</span>
            <input
              type={showPasswords ? "text" : "password"}
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

          <div className="password-change-actions">
            <button className="secondary" type="button" onClick={onClose} disabled={busy}>Отмена</button>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? <LoaderCircle size={17} className="spin" /> : <Save size={17} />}
              {busy ? "Сохраняем…" : "Сменить пароль"}
            </button>
          </div>
        </form>

        <div className="password-change-note"><KeyRound size={15} />Новый пароль сразу станет действующим.</div>
      </div>
    </div>
  );
}
