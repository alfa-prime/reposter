import { useCallback, useEffect, useState } from "react";
import { Play, Save } from "lucide-react";
import { api, CollectionSettings, CollectionStatus } from "../api";
import "../scheduler.css";

type FormState = Omit<CollectionSettings, "updated_at">;

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value)) : "—";
}

export function SettingsPage() {
  const [form, setForm] = useState<FormState | null>(null);
  const [status, setStatus] = useState<CollectionStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try {
      const [settings, schedulerStatus] = await Promise.all([api.collectionSettings(), api.collectionStatus()]);
      setForm((current) => current ?? {
        enabled: settings.enabled,
        interval_minutes: settings.interval_minutes,
        start_time: settings.start_time.slice(0, 5),
        end_time: settings.end_time.slice(0, 5),
        timezone: settings.timezone,
      });
      setStatus(schedulerStatus);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить расписание");
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { void api.collectionStatus().then(setStatus).catch(() => undefined); }, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function save() {
    if (!form) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await api.updateCollectionSettings(form);
      setForm({ enabled: saved.enabled, interval_minutes: saved.interval_minutes, start_time: saved.start_time.slice(0, 5), end_time: saved.end_time.slice(0, 5), timezone: saved.timezone });
      setNotice("Расписание сохранено и уже применяется.");
      setStatus(await api.collectionStatus());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось сохранить расписание");
    } finally { setBusy(false); }
  }

  async function runNow() {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.collectNow();
      setNotice(`Сбор №${result.run_id} завершён: найдено ${result.posts_found}, добавлено в очередь ${result.queue_items_created}.`);
      setStatus(await api.collectionStatus());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось запустить сбор");
    } finally { setBusy(false); }
  }

  return (
    <section className="settings-page scheduler-page">
      <header className="settings-page-head scheduler-head">
        <div><p className="eyebrow">НАСТРОЙКИ · РЕДАКЦИОННАЯ ОЧЕРЕДЬ</p><h1>Расписание планировщика</h1></div>
        <button className="secondary" disabled={busy} onClick={() => void runNow()}><Play size={16} />Собрать сейчас</button>
      </header>

      {(error || notice) && <div className={error ? "toast error" : "toast"}>{error || notice}<button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

      <div className="scheduler-status-grid">
        <div className="scheduler-stat"><span>Состояние</span><strong className={status?.enabled ? "positive" : "muted"}>{status?.running ? "Идёт сбор" : status?.enabled ? "Включён" : "Отключён"}</strong></div>
        <div className="scheduler-stat"><span>Следующий запуск</span><strong>{formatDate(status?.next_run_at)}</strong></div>
        <div className="scheduler-stat"><span>Последний успешный</span><strong>{formatDate(status?.last_success_at)}</strong></div>
        <div className="scheduler-stat"><span>Ошибок подряд</span><strong className={status?.consecutive_failures ? "negative" : "positive"}>{status?.consecutive_failures ?? 0}</strong></div>
      </div>

      {form && <div className="scheduler-form-card">
        <div className="scheduler-form-title">
          <div><strong>Автоматический сбор</strong><span>После включения новые публикации будут проверяться только внутри рабочего окна.</span></div>
          <label className="scheduler-toggle"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} /><span /></label>
        </div>

        <div className="scheduler-fields">
          <label>Начало окна<input type="time" value={form.start_time} onChange={(event) => setForm({ ...form, start_time: event.target.value })} /></label>
          <label>Конец окна<input type="time" value={form.end_time} onChange={(event) => setForm({ ...form, end_time: event.target.value })} /></label>
          <label>Периодичность<select value={form.interval_minutes} onChange={(event) => setForm({ ...form, interval_minutes: Number(event.target.value) })}>{[5, 10, 15, 30, 60, 120].map((minutes) => <option key={minutes} value={minutes}>{minutes < 60 ? `Каждые ${minutes} мин` : `Каждые ${minutes / 60} ч`}</option>)}</select></label>
          <label>Часовой пояс<select value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })}><option value="Europe/Moscow">Москва (UTC+3)</option><option value="Europe/Kaliningrad">Калининград (UTC+2)</option><option value="Asia/Yekaterinburg">Екатеринбург (UTC+5)</option><option value="Asia/Novosibirsk">Новосибирск (UTC+7)</option><option value="Asia/Vladivostok">Владивосток (UTC+10)</option></select></label>
        </div>
        <p className="scheduler-hint">Окно может переходить через полночь: сочетание 20:00–08:00 означает работу вечером и ночью. Одинаковое время начала и окончания не допускается.</p>
        <div className="scheduler-actions"><button className="primary" disabled={busy} onClick={() => void save()}><Save size={16} />Сохранить расписание</button></div>
      </div>}
    </section>
  );
}
