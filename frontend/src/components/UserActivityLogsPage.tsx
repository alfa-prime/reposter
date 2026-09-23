import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw, ShieldCheck } from "lucide-react";
import { AdminUser, api, AuditEvent } from "../api";
import "../scheduler.css";

const actionLabels: Record<string, string> = {
  "user.created": "Создан пользователь",
  "user.updated": "Изменён пользователь",
  "user.targets.changed": "Изменён доступ к каналам",
  "user.password.reset": "Сброшен пароль",
  "user.sessions.revoked": "Завершены сессии",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value));
}

function userLabel(name: string | null, username: string | null, id: number | null) {
  if (name && username) return `${name} · @${username}`;
  if (name) return name;
  return id ? `Пользователь #${id}` : "Система";
}

function eventDetails(event: AuditEvent): string {
  if (event.action === "user.targets.changed") {
    const added = Array.isArray(event.details.added_target_ids) ? event.details.added_target_ids.length : 0;
    const removed = Array.isArray(event.details.removed_target_ids) ? event.details.removed_target_ids.length : 0;
    return `Добавлено каналов: ${added}, удалено: ${removed}`;
  }
  if (event.action === "user.sessions.revoked") return `Завершено сессий: ${String(event.details.revoked_sessions ?? 0)}`;
  if (event.action === "user.created") return "Создана новая учётная запись";
  if (event.action === "user.password.reset") return "Установлен временный пароль и завершены активные сессии";
  if (event.action === "user.updated") {
    const labels: Record<string, string> = { display_name: "имя", role_codes: "роли", is_active: "статус" };
    const fields = Object.keys(event.details).map((key) => labels[key] ?? key);
    return fields.length ? `Изменено: ${fields.join(", ")}` : "Профиль изменён";
  }
  return event.action;
}

export function UserActivityLogsPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [actorUserId, setActorUserId] = useState(0);
  const [action, setAction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const [page, userData] = await Promise.all([
        api.auditEvents({ offset, limit, actorUserId: actorUserId || undefined, action: action || undefined }),
        users.length ? Promise.resolve(users) : api.adminUsers(),
      ]);
      setEvents(page.items); setTotal(page.total); setUsers(userData);
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Не удалось загрузить журнал"); }
    finally { setBusy(false); }
  }, [action, actorUserId, limit, offset, users]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setOffset(0); }, [action, actorUserId, limit]);

  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <section className="settings-page scheduler-page">
      <header className="settings-page-head scheduler-head">
        <div><p className="eyebrow">АДМИНИСТРИРОВАНИЕ · ЖУРНАЛЫ</p><h1>Журнал пользователей</h1></div>
        <button className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16} className={busy ? "spin" : ""} />Обновить</button>
      </header>
      {error && <div className="toast error">{error}<button onClick={() => setError("")}>×</button></div>}

      <div className="logs-section-title"><strong>Действия с учётными записями</strong><span>Кто, когда и какие административные изменения выполнил.</span></div>
      <div className="log-toolbar">
        <label>Кто выполнил<select value={actorUserId} onChange={(event) => setActorUserId(Number(event.target.value))}><option value={0}>Все пользователи</option>{users.map((user) => <option key={user.user_id} value={user.user_id}>{user.display_name} · @{user.username}</option>)}</select></label>
        <label>Действие<select value={action} onChange={(event) => setAction(event.target.value)}><option value="">Все действия</option>{Object.entries(actionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>На странице<select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>{[10, 20, 40].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      </div>

      <div className="user-audit-list">
        {events.length === 0 && !busy && <div className="scheduler-log-empty">В журнале пока нет подходящих событий.</div>}
        {events.map((event) => <article className="user-audit-card" key={event.audit_event_id}>
          <span className="user-audit-icon"><ShieldCheck size={17} /></span>
          <div className="user-audit-main"><strong>{actionLabels[event.action] ?? event.action}</strong><span>{eventDetails(event)}</span></div>
          <div className="user-audit-person"><small>Выполнил</small><strong>{userLabel(event.actor_name, event.actor_username, event.actor_user_id)}</strong></div>
          <div className="user-audit-person"><small>Пользователь</small><strong>{userLabel(event.subject_name, event.subject_username, event.subject_id)}</strong></div>
          <time>{formatDate(event.created_at)}</time>
        </article>)}
      </div>

      <div className="log-pagination"><span>События {total ? offset + 1 : 0}–{Math.min(offset + limit, total)} из {total}</span><div><button className="icon-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}><ChevronLeft size={17} /></button><strong>{page} / {pages}</strong><button className="icon-button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}><ChevronRight size={17} /></button></div></div>
    </section>
  );
}
