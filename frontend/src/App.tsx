import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  Bot,
  ChevronRight,
  CircleDot,
  Database,
  ExternalLink,
  FileText,
  LayoutDashboard,
  Radio,
  RefreshCw,
  Save,
  Settings,
  Sparkles,
} from "lucide-react";
import { api, getApiKey, QueueItem, setApiKey, Source, Target } from "./api";

type Section = "dashboard" | "queue" | "targets" | "sources";

const statusLabels: Record<string, string> = {
  pending: "В работе",
  rewriting: "Рерайт",
  awaiting_moderation: "На модерации",
  approved: "Одобрено",
  rejected: "Отклонено",
  scheduled: "Запланировано",
  failed: "Ошибка",
};

function shortDate(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function App() {
  const [section, setSection] = useState<Section>("queue");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [draftText, setDraftText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [apiKey, setApiKeyState] = useState(getApiKey());

  const activeTargets = useMemo(() => targets.filter((item) => item.is_active).length, [targets]);
  const activeSources = useMemo(() => sources.filter((item) => item.is_active).length, [sources]);

  async function loadAll() {
    setBusy(true);
    setError("");
    try {
      const [queueData, targetData, sourceData] = await Promise.all([
        api.queue(),
        api.targets(),
        api.sources(),
      ]);
      setQueue(queueData);
      setTargets(targetData);
      setSources(sourceData);
      if (selected) {
        const updated = queueData.find((item) => item.queue_item_id === selected.queue_item_id) ?? null;
        setSelected(updated);
        setDraftText(updated?.rewritten_text ?? updated?.original_text ?? "");
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить данные");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  function openItem(item: QueueItem) {
    setSelected(item);
    setDraftText(item.rewritten_text ?? item.original_text ?? "");
  }

  async function runAction(action: () => Promise<QueueItem>, message: string) {
    setBusy(true);
    setError("");
    try {
      const item = await action();
      setSelected(item);
      setDraftText(item.rewritten_text ?? item.original_text ?? "");
      setQueue((items) => items.map((current) => current.queue_item_id === item.queue_item_id ? item : current));
      setNotice(message);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Операция не выполнена");
    } finally {
      setBusy(false);
    }
  }

  async function collectNow() {
    setBusy(true);
    setError("");
    try {
      const result = await api.collectNow();
      setNotice(`Проверено источников: ${result.sources_checked}. Новых постов: ${result.posts_created}.`);
      await loadAll();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Сбор не выполнен");
    } finally {
      setBusy(false);
    }
  }

  function saveKey() {
    setApiKey(apiKey);
    setNotice("API-ключ сохранён в браузере");
    void loadAll();
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Sparkles size={19} /></div>
          <div><strong>Reposter</strong><span>редакционная система</span></div>
        </div>

        <nav>
          <button onClick={() => setSection("dashboard")} className={section === "dashboard" ? "active" : ""}><LayoutDashboard size={18} />Обзор</button>
          <button onClick={() => setSection("queue")} className={section === "queue" ? "active" : ""}><FileText size={18} />Очередь</button>
          <button onClick={() => setSection("targets")} className={section === "targets" ? "active" : ""}><Radio size={18} />Каналы</button>
          <button onClick={() => setSection("sources")} className={section === "sources" ? "active" : ""}><Database size={18} />Источники</button>
        </nav>

        <div className="sidebar-foot">
          <div className="api-key-block">
            <label>API-ключ</label>
            <div className="key-row">
              <input value={apiKey} onChange={(event) => setApiKeyState(event.target.value)} type="password" placeholder="X-API-Key" />
              <button onClick={saveKey} title="Сохранить ключ"><Save size={16} /></button>
            </div>
          </div>
          <div className="system-state"><CircleDot size={14} /> Backend connected</div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">NEWS REPOSTER</p>
            <h1>{section === "queue" ? "Редакционная очередь" : section === "targets" ? "Целевые каналы" : section === "sources" ? "Источники" : "Обзор"}</h1>
          </div>
          <button className="primary" onClick={() => void collectNow()} disabled={busy}><RefreshCw size={17} className={busy ? "spin" : ""} />Собрать сейчас</button>
        </header>

        {(error || notice) && <div className={error ? "toast error" : "toast"}>{error || notice}<button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

        {section === "dashboard" && (
          <section className="dashboard-grid">
            <article className="metric"><span>Активные каналы</span><strong>{activeTargets}</strong><small>из {targets.length}</small></article>
            <article className="metric"><span>Источники</span><strong>{activeSources}</strong><small>из {sources.length}</small></article>
            <article className="metric"><span>В очереди</span><strong>{queue.length}</strong><small>постов</small></article>
            <article className="hero-card"><Bot size={24}/><div><h3>Рерайт подключим следующим этапом</h3><p>Сейчас прототип уже собирает посты и фото, раскладывает по каналам и даёт редактору управлять очередью.</p></div></article>
          </section>
        )}

        {section === "queue" && (
          <section className="queue-layout">
            <div className="queue-list">
              {queue.length === 0 && <div className="empty">Очередь пока пуста</div>}
              {queue.map((item) => (
                <button key={item.queue_item_id} className={`queue-card ${selected?.queue_item_id === item.queue_item_id ? "selected" : ""}`} onClick={() => openItem(item)}>
                  <div className="queue-card-head"><span className={`badge status-${item.status}`}>{statusLabels[item.status] ?? item.status}</span><time>{shortDate(item.source_published_at)}</time></div>
                  <h3>{item.target_name ?? `Канал #${item.target_id}`}</h3>
                  <p>{item.original_text || "Пост без текста"}</p>
                  <div className="queue-card-bottom"><span>{item.photos.length ? `${item.photos.length} фото` : "без фото"}</span><ChevronRight size={16}/></div>
                </button>
              ))}
            </div>

            <div className="editor-panel">
              {!selected ? <div className="empty large"><Archive size={34}/><h3>Выберите пост</h3><p>Здесь появятся исходник, фотографии и редакционный текст.</p></div> : (
                <>
                  <div className="editor-head"><div><span className={`badge status-${selected.status}`}>{statusLabels[selected.status] ?? selected.status}</span><h2>{selected.target_name ?? `Канал #${selected.target_id}`}</h2></div>{selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer">VK <ExternalLink size={14}/></a>}</div>
                  {selected.photos.length > 0 && <div className="photo-strip">{selected.photos.map((photo) => <img key={photo.attachment_id} src={photo.source_url} alt="Вложение поста" />)}</div>}
                  <div className="text-block"><label>Исходный текст</label><div className="original-text">{selected.original_text || "—"}</div></div>
                  <div className="text-block"><label>Текст для публикации</label><textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} rows={11} /></div>
                  <div className="actions">
                    <button className="secondary" onClick={() => void runAction(() => api.updateQueueText(selected.queue_item_id, draftText), "Текст сохранён")}>Сохранить</button>
                    {selected.status === "pending" && <button className="primary" onClick={() => void runAction(async () => { await api.updateQueueText(selected.queue_item_id, draftText); return api.submit(selected.queue_item_id); }, "Отправлено на модерацию")}>На модерацию</button>}
                    {selected.status === "awaiting_moderation" && <><button className="danger" onClick={() => void runAction(() => api.reject(selected.queue_item_id), "Пост отклонён")}>Отклонить</button><button className="primary" onClick={() => void runAction(() => api.approve(selected.queue_item_id), "Пост одобрен")}>Одобрить</button></>}
                    {["rejected", "approved", "scheduled", "awaiting_moderation"].includes(selected.status) && <button className="secondary" onClick={() => void runAction(() => api.reopen(selected.queue_item_id), "Пост возвращён в работу")}>Вернуть в работу</button>}
                  </div>
                </>
              )}
            </div>
          </section>
        )}

        {section === "targets" && <section className="table-card"><div className="table-head"><h2>Каналы</h2><span>{targets.length} всего</span></div>{targets.map((item) => <div className="entity-row" key={item.target_id}><div className="entity-icon"><Radio size={18}/></div><div className="entity-main"><strong>{item.name}</strong><span>{item.platform} · {item.external_id}</span></div><span className={item.is_active ? "switch-label on" : "switch-label"}>{item.is_active ? "Активен" : "Выключен"}</span></div>)}</section>}

        {section === "sources" && <section className="table-card"><div className="table-head"><h2>Источники</h2><span>{sources.length} всего</span></div>{sources.map((item) => <div className="entity-row" key={item.source_id}><div className="entity-icon"><Database size={18}/></div><div className="entity-main"><strong>{item.name}</strong><span>{item.platform} · {item.url}</span></div><span className={item.is_active ? "switch-label on" : "switch-label"}>{item.is_active ? "Активен" : "Выключен"}</span></div>)}</section>}
      </main>
    </div>
  );
}
