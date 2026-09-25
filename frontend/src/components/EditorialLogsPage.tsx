import { useCallback, useEffect, useState } from "react";
import { BookOpenCheck, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { AdminUser, api, EditorialAuditEvent, Target } from "../api";
import "../scheduler.css";

const labels: Record<string, string> = {
  "editorial.created": "Добавлен в очередь", "editorial.edited": "Отредактирован",
  "editorial.rewritten": "Переписан с ИИ", "editorial.submitted": "Отправлен на модерацию",
  "editorial.approved": "Одобрен", "editorial.rejected": "Отклонён",
  "editorial.reopened": "Возвращён в работу", "editorial.scheduled": "Запланирован",
  "editorial.published": "Опубликован", "editorial.deleted": "Удалён",
  "editorial.publication_unknown": "Результат публикации неизвестен",
  "editorial.publication_checked": "Публикация проверена в MAX",
  "editorial.publication_reconciled": "Публикация найдена в MAX",
  "editorial.publication_marked_manually": "Публикация подтверждена вручную",
  "editorial.publication_retried": "Публикация отправлена повторно",
  "editorial.publication_returned_to_work": "Возвращён в работу после проверки",
};

const formatDate = (value: string) => new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value));
const actorLabel = (event: EditorialAuditEvent) => event.actor_name ? `${event.actor_name}${event.actor_username ? ` · @${event.actor_username}` : ""}` : "Система";

function detail(event: EditorialAuditEvent) {
  if (event.action === "editorial.edited") {
    const fields = Array.isArray(event.details.changed_fields) ? event.details.changed_fields : [];
    const names: Record<string, string> = { rewritten_text: "текст", signature_text: "подпись" };
    return `Изменено: ${fields.map((field) => names[String(field)] ?? String(field)).join(", ")}`;
  }
  if (event.action === "editorial.scheduled" && event.details.scheduled_at) return `На ${formatDate(String(event.details.scheduled_at))}`;
  if (event.action === "editorial.publication_checked") {
    const outcomes: Record<string, string> = { found: "найдена", not_found: "не найдена", ambiguous: "найдено несколько совпадений" };
    return `Результат: ${outcomes[String(event.details.outcome)] ?? String(event.details.outcome ?? "проверено")}`;
  }
  const before = event.details.previous_status;
  const after = event.details.status;
  return before && after ? `${String(before)} → ${String(after)}` : `Материал #${event.queue_item_id}`;
}

export function EditorialLogsPage({ onOpenMaterial }: { onOpenMaterial: (queueItemId: number) => void }) {
  const [events, setEvents] = useState<EditorialAuditEvent[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [total, setTotal] = useState(0); const [offset, setOffset] = useState(0); const [limit, setLimit] = useState(20);
  const [actor, setActor] = useState(0); const [target, setTarget] = useState(0); const [action, setAction] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [dateFrom, setDateFrom] = useState(""); const [dateTo, setDateTo] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const [page, userData, targetData] = await Promise.all([
        api.editorialAuditEvents({ offset, limit, actorUserId: actor || undefined, targetId: target || undefined, queueItemId: Number(materialId) || undefined, action: action || undefined, dateFrom: dateFrom ? new Date(`${dateFrom}T00:00:00`).toISOString() : undefined, dateTo: dateTo ? new Date(`${dateTo}T23:59:59`).toISOString() : undefined }),
        users.length ? Promise.resolve(users) : api.adminUsers(), targets.length ? Promise.resolve(targets) : api.targets(),
      ]);
      setEvents(page.items); setTotal(page.total); setUsers(userData); setTargets(targetData);
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Не удалось загрузить редакционный журнал"); }
    finally { setBusy(false); }
  }, [action, actor, dateFrom, dateTo, limit, materialId, offset, target, targets, users]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setOffset(0); }, [action, actor, dateFrom, dateTo, limit, materialId, target]);
  const page = Math.floor(offset / limit) + 1; const pages = Math.max(1, Math.ceil(total / limit));

  return <section className="settings-page scheduler-page">
    <header className="settings-page-head scheduler-head"><div><p className="eyebrow">АДМИНИСТРИРОВАНИЕ · ЖУРНАЛЫ</p><h1>Редакционный журнал</h1></div><button className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16} className={busy ? "spin" : ""} />Обновить</button></header>
    {error && <div className="toast error">{error}<button onClick={() => setError("")}>×</button></div>}
    <div className="logs-section-title"><strong>История работы с материалами</strong><span>Редактирование, модерация, планирование и публикация.</span></div>
    <div className="log-toolbar editorial-log-toolbar">
      <label>Сотрудник<select value={actor} onChange={(e) => setActor(Number(e.target.value))}><option value={0}>Все</option>{users.map((u) => <option key={u.user_id} value={u.user_id}>{u.display_name}</option>)}</select></label>
      <label>Канал<select value={target} onChange={(e) => setTarget(Number(e.target.value))}><option value={0}>Все</option>{targets.map((t) => <option key={t.target_id} value={t.target_id}>{t.name}</option>)}</select></label>
      <label>Действие<select value={action} onChange={(e) => setAction(e.target.value)}><option value="">Все</option>{Object.entries(labels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>Материал<input type="number" min="1" value={materialId} onChange={(e) => setMaterialId(e.target.value)} placeholder="Например, 1836" /></label>
      <label>С даты<input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></label><label>По дату<input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></label>
      <label>На странице<select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>{[10,20,40].map((v) => <option key={v}>{v}</option>)}</select></label>
    </div>
    <div className="user-audit-list">{!busy && events.length === 0 && <div className="scheduler-log-empty">Событий пока нет.</div>}{events.map((event) => <article className="user-audit-card editorial-audit-card" key={event.audit_event_id}><span className="user-audit-icon"><BookOpenCheck size={17}/></span><div className="user-audit-main"><strong>{labels[event.action] ?? event.action}</strong><span>{detail(event)}</span></div><div className="user-audit-person"><small>Сотрудник</small><strong>{actorLabel(event)}</strong></div><div className="user-audit-person"><small>Канал</small><strong>{event.target_name ?? `Канал #${event.target_id ?? "—"}`}</strong></div><div className="user-audit-person"><small>Материал</small>{event.material_exists ? <button className="audit-material-link" onClick={() => onOpenMaterial(event.queue_item_id)}>#{event.queue_item_id}</button> : <strong>#{event.queue_item_id} · удалён</strong>}</div><time>{formatDate(event.created_at)}</time></article>)}</div>
    <div className="log-pagination"><span>События {total ? offset + 1 : 0}–{Math.min(offset + limit, total)} из {total}</span><div><button className="icon-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset-limit))}><ChevronLeft size={17}/></button><strong>{page} / {pages}</strong><button className="icon-button" disabled={offset+limit >= total} onClick={() => setOffset(offset+limit)}><ChevronRight size={17}/></button></div></div>
  </section>;
}
