import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { AdminUser, api, AuditEvent } from "../api";
import { useJournalPage } from "../useJournalPage";
import { JournalPagination } from "./JournalPagination";
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
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [limit, setLimit] = useState(20);
  const [actorUserId, setActorUserId] = useState(0);
  const [action, setAction] = useState("");

  const fetchPage = useCallback((cursor: string | null, signal: AbortSignal) =>
    api.auditEvents({ cursor, signal, limit, actorUserId: actorUserId || undefined, action: action || undefined }),
    [action, actorUserId, limit]);
  const journal = useJournalPage(JSON.stringify([action, actorUserId, limit]), fetchPage);
  const { items: events, busy, error, setError, load } = journal;
  useEffect(() => {
    let active = true;
    void api.adminUsers().then((data) => { if (active) setUsers(data); })
      .catch((exc: unknown) => { if (active) setError(exc instanceof Error ? exc.message : "Не удалось загрузить пользователей"); });
    return () => { active = false; };
  }, [setError]);

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

      <JournalPagination {...journal} count={events.length} limit={limit} label="События" />
    </section>
  );
}
