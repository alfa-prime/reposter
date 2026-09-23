import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, RefreshCw } from "lucide-react";
import { api, CollectionRun, CollectionRunDetail } from "../api";
import "../scheduler.css";

const statusLabels: Record<string, string> = { running: "Выполняется", success: "Успешно", partial: "Частично", failed: "Ошибка", skipped: "Пропущен", interrupted: "Прерван", no_changes: "Без изменений" };
const triggerLabels: Record<string, string> = { manual: "Вручную", scheduled: "По расписанию" };

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value)) : "—";
}

function duration(run: CollectionRun) {
  if (!run.finished_at) return "—";
  const seconds = Math.max(0, Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000));
  return seconds < 60 ? `${seconds} сек` : `${Math.floor(seconds / 60)} мин ${seconds % 60} сек`;
}

export function SchedulerLogsPage() {
  const [runs, setRuns] = useState<CollectionRun[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(20);
  const [status, setStatus] = useState("");
  const [trigger, setTrigger] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<CollectionRunDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const page = await api.collectionRuns({ offset, limit, status: status || undefined, trigger: trigger || undefined });
      setRuns(page.items); setTotal(page.total);
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Не удалось загрузить журнал"); }
    finally { setBusy(false); }
  }, [offset, limit, status, trigger]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setOffset(0); }, [limit, status, trigger]);

  async function toggle(runId: number) {
    if (expanded === runId) { setExpanded(null); setDetail(null); return; }
    setExpanded(runId); setDetail(null);
    try { setDetail(await api.collectionRun(runId)); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Не удалось загрузить детали запуска"); }
  }

  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <section className="settings-page scheduler-page">
      <header className="settings-page-head scheduler-head">
        <div><p className="eyebrow">АДМИНИСТРИРОВАНИЕ · ЖУРНАЛЫ</p><h1>Журналы</h1></div>
        <button className="secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={16} className={busy ? "spin" : ""} />Обновить</button>
      </header>
      {error && <div className="toast error">{error}<button onClick={() => setError("")}>×</button></div>}

      <div className="logs-section-title">
        <strong>Журнал планировщика</strong>
        <span>История ручных и автоматических запусков сбора.</span>
      </div>

      <div className="log-toolbar">
        <label>Результат<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Все</option><option value="success">Успешно</option><option value="partial">Частично</option><option value="failed">Ошибка</option><option value="skipped">Пропущен</option><option value="interrupted">Прерван</option></select></label>
        <label>Запуск<select value={trigger} onChange={(event) => setTrigger(event.target.value)}><option value="">Все</option><option value="scheduled">По расписанию</option><option value="manual">Вручную</option></select></label>
        <label>На странице<select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>{[10, 20, 40].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      </div>

      <div className="scheduler-log-list">
        {runs.length === 0 && !busy && <div className="scheduler-log-empty">Запусков пока нет. После ручного или автоматического сбора они появятся здесь.</div>}
        {runs.map((run) => <div className="scheduler-log-card" key={run.collection_run_id}>
          <button className="scheduler-log-summary" onClick={() => void toggle(run.collection_run_id)}>
            <span className={`run-status run-status-${run.status}`}>{statusLabels[run.status]}</span>
            <span><small>Запуск</small><strong>№{run.collection_run_id} · {triggerLabels[run.trigger]}</strong></span>
            <span><small>Начало</small><strong>{formatDate(run.started_at)}</strong></span>
            <span><small>Длительность</small><strong>{duration(run)}</strong></span>
            <span><small>Найдено / очередь</small><strong>{run.posts_found} / {run.queue_items_created}</strong></span>
            <span><small>Источники</small><strong>{run.sources_succeeded} успешно · {run.sources_failed} ошибок</strong></span>
            {expanded === run.collection_run_id ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
          </button>
          {expanded === run.collection_run_id && <div className="scheduler-log-detail">
            {!detail && <div className="scheduler-detail-loading">Загружаем результаты источников…</div>}
            {detail?.error_message && <div className="scheduler-run-error">{detail.error_message}</div>}
            {detail?.source_runs.map((source) => <div className="source-run-row" key={source.collection_source_run_id}>
              <span className={`run-status run-status-${source.status}`}>{statusLabels[source.status]}</span>
              <div className="source-run-name"><strong>{source.source_name}</strong><a href={source.source_url} target="_blank" rel="noreferrer">{source.source_url}</a></div>
              <span><small>Точка продолжения</small><strong>{source.last_post_id_before ?? "—"} → {source.last_post_id_after ?? "—"}</strong></span>
              <span><small>Найдено / создано</small><strong>{source.posts_found} / {source.posts_created}</strong></span>
              {source.error_message && <p>{source.error_type}: {source.error_message}</p>}
            </div>)}
          </div>}
        </div>)}
      </div>

      <div className="log-pagination"><span>Запуски {total ? offset + 1 : 0}–{Math.min(offset + limit, total)} из {total}</span><div><button className="icon-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}><ChevronLeft size={17} /></button><strong>{page} / {pages}</strong><button className="icon-button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}><ChevronRight size={17} /></button></div></div>
    </section>
  );
}
