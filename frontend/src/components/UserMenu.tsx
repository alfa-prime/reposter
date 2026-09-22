import { useEffect, useRef, useState } from "react";
import { KeyRound, LogOut, ShieldOff } from "lucide-react";
import { useAuth } from "../auth";

type Props = {
  onChangePassword: () => void;
};

function initials(displayName: string, username: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  const value = parts.length > 1
    ? `${parts[0][0]}${parts[1][0]}`
    : (parts[0] ?? username).slice(0, 2);
  return value.toLocaleUpperCase("ru-RU");
}

export function UserMenu({ onChangePassword }: Props) {
  const { user, logout } = useAuth();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const [busy, setBusy] = useState(false);
  const [confirmAll, setConfirmAll] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    function closeOnOutsideClick(event: PointerEvent) {
      if (!detailsRef.current?.contains(event.target as Node)) {
        detailsRef.current?.removeAttribute("open");
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") detailsRef.current?.removeAttribute("open");
    }

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  if (user === null) return null;

  const roleLabel = user.roles.map((role) => role.name).join(", ") || "Без роли";

  async function performLogout(allSessions: boolean) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await logout(allSessions);
      detailsRef.current?.removeAttribute("open");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось завершить сессию");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="user-menu" ref={detailsRef} onToggle={() => setConfirmAll(false)}>
      <summary title={`${user.display_name} · ${roleLabel}`}>
        <span className="user-avatar" aria-hidden="true">
          {user.avatar_url
            ? <img src={user.avatar_url} alt="" decoding="async" />
            : initials(user.display_name, user.username)}
        </span>
        <span className="user-summary-text">
          <strong>{user.display_name}</strong>
          <small>{roleLabel}</small>
        </span>
      </summary>

      <div className="user-menu-popover">
        <div className="user-menu-identity">
          <strong>{user.display_name}</strong>
          <span>@{user.username}</span>
        </div>

        {error && <p className="user-menu-error" role="alert">{error}</p>}

        {confirmAll ? (
          <div className="user-menu-confirm">
            <p>Завершить все сессии на всех устройствах?</p>
            <div>
              <button type="button" onClick={() => setConfirmAll(false)} disabled={busy}>Отмена</button>
              <button type="button" className="confirm" onClick={() => void performLogout(true)} disabled={busy}>Завершить</button>
            </div>
          </div>
        ) : (
          <div className="user-menu-actions">
            <button type="button" onClick={() => { detailsRef.current?.removeAttribute("open"); onChangePassword(); }} disabled={busy}>
              <KeyRound size={16} />Сменить пароль
            </button>
            <button type="button" onClick={() => void performLogout(false)} disabled={busy}>
              <LogOut size={16} />Выйти
            </button>
            <button type="button" onClick={() => setConfirmAll(true)} disabled={busy}>
              <ShieldOff size={16} />Завершить все сессии
            </button>
          </div>
        )}
      </div>
    </details>
  );
}
