import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Archive,
  Bot,
  ChevronRight,
  CircleDot,
  Database,
  ExternalLink,
  FileText,
  LayoutDashboard,
  Link2,
  Plus,
  Radio,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { api, QueueItem, Source, Target, TargetSource } from "./api";

type Section = "dashboard" | "queue" | "targets" | "sources";
type ModalKind = "target" | "source" | null;

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

function ensureFormValid(form: HTMLFormElement, setError: (message: string) => void): boolean {
  if (form.checkValidity()) return true;
  setError("Заполните обязательные поля, отмеченные звёздочкой.");
  form.reportValidity();
  return false;
}

export function App() {
  const [section, setSection] = useState<Section>("queue");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null);
  const [targetSources, setTargetSources] = useState<TargetSource[]>([]);
  const [draftText, setDraftText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState<ModalKind>(null);

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
      if (selectedTarget) {
        const updatedTarget = targetData.find((item) => item.target_id === selectedTarget.target_id) ?? null;
        setSelectedTarget(updatedTarget);
        if (updatedTarget) setTargetSources(await api.targetSources(updatedTarget.target_id));
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить данные");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadAll(); }, []);

  function openItem(item: QueueItem) {
    setSelected(item);
    setDraftText(item.rewritten_text ?? item.original_text ?? "");
  }

  async function openTarget(item: Target) {
    setSelectedTarget(item);
    setBusy(true);
    setError("");
    try {
      setTargetSources(await api.targetSources(item.target_id));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить источники канала");
    } finally {
      setBusy(false);
    }
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
    setNotice("");
    try {
      const result = await api.collectNow();
      if (result.sources_checked === 0) {
        if (sources.length === 0) {
          setSection("sources");
          setError("Сбор не запущен: сначала добавьте хотя бы один источник VK.");
        } else if (targets.length === 0) {
          setSection("targets");
          setError("Сбор не запущен: сначала добавьте целевой канал.");
        } else {
          setSection("targets");
          const firstActiveTarget = targets.find((item) => item.is_active) ?? targets[0];
          if (firstActiveTarget) await openTarget(firstActiveTarget);
          setError("Сбор не запущен: источник ещё не подключён к активному каналу. Выберите канал и нажмите «Подключить источник».");
        }
      } else if (result.errors > 0) {
        setError(`Сбор завершён с ошибками: проверено ${result.sources_checked}, ошибок ${result.errors}.`);
      } else {
        setNotice(`Проверено источников: ${result.sources_checked}. Новых постов: ${result.posts_created}. В очередь добавлено: ${result.queue_items_created}.`);
      }
      await loadAll();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Сбор не выполнен");
    } finally {
      setBusy(false);
    }
  }

  async function createTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!ensureFormValid(form, setError)) return;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    try {
      const created = await api.createTarget({
        name: String(data.get("name") ?? "").trim(),
        platform: String(data.get("platform") ?? "max"),
        external_id: String(data.get("external_id") ?? "").trim(),
        url: String(data.get("url") ?? "").trim() || null,
        is_active: true,
      });
      setModal(null);
      setNotice("Канал добавлен. Теперь подключите к нему источник.");
      await loadAll();
      setSection("targets");
      await openTarget(created);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось добавить канал");
    } finally {
      setBusy(false);
    }
  }

  async function createSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!ensureFormValid(form, setError)) return;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await api.createSource({
        name: String(data.get("name") ?? "").trim(),
        platform: String(data.get("platform") ?? "vk"),
        url: String(data.get("url") ?? "").trim(),
        is_active: true,
      });
      setModal(null);
      setNotice("Источник добавлен. Чтобы он участвовал в сборе, подключите его к каналу.");
      await loadAll();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось добавить источник");
    } finally {
      setBusy(false);
    }
  }

  async function attachSource(sourceId: number) {
    if (!selectedTarget) return;
    setBusy(true);
    setError("");
    try {
      await api.attachSource(selectedTarget.target_id, sourceId);
      setTargetSources(await api.targetSources(selectedTarget.target_id));
      setNotice("Источник подключён к каналу. Теперь его можно собирать.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось подключить источник");
    } finally {
      setBusy(false);
    }
  }

  const attachedSourceIds = new Set(targetSources.map((item) => item.source_id));

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Sparkles size={19} /></div><div><strong>Reposter</strong><span>редакционная система</span></div></div>
        <nav>
          <button onClick={() => setSection("dashboard")} className={section === "dashboard" ? "active" : ""}><LayoutDashboard size={18} />Обзор</button>
          <button onClick={() => setSection("queue")} className={section === "queue" ? "active" : ""}><FileText size={18} />Очередь</button>
          <button onClick={() => setSection("targets")} className={section === "targets" ? "active" : ""}><Radio size={18} />Каналы</button>
          <button onClick={() => setSection("sources")} className={section === "sources" ? "active" : ""}><Database size={18} />Источники</button>
        </nav>
        <div className="sidebar-foot"><div className="system-state"><CircleDot size={14} /> Backend connected</div></div>
      </aside>

      <main className="workspace">
        <header className="topbar"><div><p className="eyebrow">NEWS REPOSTER</p><h1>{section === "queue" ? "Редакционная очередь" : section === "targets" ? "Целевые каналы" : section === "sources" ? "Источники" : "Обзор"}</h1></div><button className="primary" onClick={() => void collectNow()} disabled={busy}><RefreshCw size={17} className={busy ? "spin" : ""} />Собрать сейчас</button></header>

        {(error || notice) && <div className={error ? "toast error" : "toast"}>{error || notice}<button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

        {section === "dashboard" && <section className="dashboard-grid">
          <article className="metric"><span>Активные каналы</span><strong>{activeTargets}</strong><small>из {targets.length}</small></article>
          <article className="metric"><span>Источники</span><strong>{activeSources}</strong><small>из {sources.length}</small></article>
          <article className="metric"><span>В очереди</span><strong>{queue.length}</strong><small>постов</small></article>
          <article className="hero-card"><Bot size={24}/><div><h3>Рерайт подключим следующим этапом</h3><p>Сейчас прототип уже собирает посты и фото, раскладывает по каналам и даёт редактору управлять очередью.</p></div></article>
        </section>}

        {section === "queue" && <section className="queue-layout">
          <div className="queue-list">{queue.length === 0 && <div className="empty">Очередь пока пуста</div>}{queue.map((item) => <button key={item.queue_item_id} className={`queue-card ${selected?.queue_item_id === item.queue_item_id ? "selected" : ""}`} onClick={() => openItem(item)}><div className="queue-card-head"><span className={`badge status-${item.status}`}>{statusLabels[item.status] ?? item.status}</span><time>{shortDate(item.source_published_at)}</time></div><h3>{item.target_name ?? `Канал #${item.target_id}`}</h3><p>{item.original_text || "Пост без текста"}</p><div className="queue-card-bottom"><span>{item.photos.length ? `${item.photos.length} фото` : "без фото"}</span><ChevronRight size={16}/></div></button>)}</div>
          <div className="editor-panel">{!selected ? <div className="empty large"><Archive size={34}/><h3>Выберите пост</h3><p>Здесь появятся исходник, фотографии и редакционный текст.</p></div> : <><div className="editor-head"><div><span className={`badge status-${selected.status}`}>{statusLabels[selected.status] ?? selected.status}</span><h2>{selected.target_name ?? `Канал #${selected.target_id}`}</h2></div>{selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer">VK <ExternalLink size={14}/></a>}</div>{selected.photos.length > 0 && <div className="photo-strip">{selected.photos.map((photo) => <img key={photo.attachment_id} src={photo.source_url} alt="Вложение поста" />)}</div>}<div className="text-block"><label>Исходный текст</label><div className="original-text">{selected.original_text || "—"}</div></div><div className="text-block"><label>Текст для публикации</label><textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} rows={11} /></div><div className="actions"><button className="secondary" onClick={() => void runAction(() => api.updateQueueText(selected.queue_item_id, draftText), "Текст сохранён")}>Сохранить</button>{selected.status === "pending" && <button className="primary" onClick={() => void runAction(async () => { await api.updateQueueText(selected.queue_item_id, draftText); return api.submit(selected.queue_item_id); }, "Отправлено на модерацию")}>На модерацию</button>}{selected.status === "awaiting_moderation" && <><button className="danger" onClick={() => void runAction(() => api.reject(selected.queue_item_id), "Пост отклонён")}>Отклонить</button><button className="primary" onClick={() => void runAction(() => api.approve(selected.queue_item_id), "Пост одобрен")}>Одобрить</button></>}{["rejected", "approved", "scheduled", "awaiting_moderation"].includes(selected.status) && <button className="secondary" onClick={() => void runAction(() => api.reopen(selected.queue_item_id), "Пост возвращён в работу")}>Вернуть в работу</button>}</div></>}</div>
        </section>}

        {section === "targets" && <section className="split-admin">
          <div className="table-card"><div className="table-head"><h2>Каналы</h2><div className="table-actions"><span>{targets.length} всего</span><button className="primary compact" onClick={() => { setError(""); setModal("target"); }}><Plus size={15}/>Добавить</button></div></div>{targets.length === 0 && <div className="empty">Каналов пока нет</div>}{targets.map((item) => <button className={`entity-row entity-button ${selectedTarget?.target_id === item.target_id ? "selected" : ""}`} key={item.target_id} onClick={() => void openTarget(item)}><div className="entity-icon"><Radio size={18}/></div><div className="entity-main"><strong>{item.name}</strong><span>{item.platform} · {item.external_id}</span></div><span className={item.is_active ? "switch-label on" : "switch-label"}>{item.is_active ? "Активен" : "Выключен"}</span><ChevronRight size={16}/></button>)}</div>
          <div className="editor-panel channel-panel">{!selectedTarget ? <div className="empty large"><Radio size={34}/><h3>Выберите канал</h3><p>Здесь будут настройки канала и его источники.</p></div> : <><div className="editor-head"><div><span className="badge">{selectedTarget.platform}</span><h2>{selectedTarget.name}</h2></div>{selectedTarget.url && <a href={selectedTarget.url} target="_blank" rel="noreferrer">Открыть <ExternalLink size={14}/></a>}</div><div className="actions"><button className="secondary" onClick={async () => { await api.updateTarget(selectedTarget.target_id, { is_active: !selectedTarget.is_active }); await loadAll(); }}>{selectedTarget.is_active ? "Отключить" : "Включить"}</button><button className="danger" onClick={async () => { if (!confirm("Удалить канал?")) return; await api.deleteTarget(selectedTarget.target_id); setSelectedTarget(null); setTargetSources([]); await loadAll(); }}><Trash2 size={15}/>Удалить</button></div><div className="section-divider" /><div className="table-head embedded"><h2>Источники канала</h2><span>{targetSources.length}</span></div>{targetSources.length === 0 && <div className="setup-hint"><strong>Подключите источник</strong><span>Без этой связи сборщик не знает, в какой канал положить найденный пост.</span></div>}{targetSources.map((link) => { const source = sources.find((item) => item.source_id === link.source_id); return <div className="entity-row" key={link.target_source_id}><div className="entity-icon"><Database size={17}/></div><div className="entity-main"><strong>{source?.name ?? `Источник #${link.source_id}`}</strong><span>{source?.url}</span></div><button className="icon-button" title="Отключить источник" onClick={async () => { await api.detachSource(selectedTarget.target_id, link.target_source_id); setTargetSources(await api.targetSources(selectedTarget.target_id)); }}><X size={16}/></button></div>; })}<div className="attach-list"><label>Подключить источник</label>{sources.filter((item) => !attachedSourceIds.has(item.source_id)).map((source) => <button key={source.source_id} className="attach-source" onClick={() => void attachSource(source.source_id)}><Link2 size={15}/><span>{source.name}</span><small>{source.platform}</small></button>)}{sources.length === 0 && <div className="empty">Сначала добавьте источник в разделе «Источники»</div>}{sources.length > 0 && sources.every((item) => attachedSourceIds.has(item.source_id)) && <div className="empty">Все источники уже подключены</div>}</div></>}</div>
        </section>}

        {section === "sources" && <section className="table-card"><div className="table-head"><h2>Источники</h2><div className="table-actions"><span>{sources.length} всего</span><button className="primary compact" onClick={() => { setError(""); setModal("source"); }}><Plus size={15}/>Добавить</button></div></div>{sources.length === 0 && <div className="empty">Источников пока нет</div>}{sources.map((item) => <div className="entity-row" key={item.source_id}><div className="entity-icon"><Database size={18}/></div><div className="entity-main"><strong>{item.name}</strong><span>{item.platform} · {item.url}</span></div><button className={item.is_active ? "switch-label on clickable" : "switch-label clickable"} onClick={async () => { await api.updateSource(item.source_id, { is_active: !item.is_active }); await loadAll(); }}>{item.is_active ? "Активен" : "Выключен"}</button><button className="icon-button danger-icon" title="Удалить" onClick={async () => { if (!confirm("Удалить источник?")) return; await api.deleteSource(item.source_id); await loadAll(); }}><Trash2 size={16}/></button></div>)}</section>}
      </main>

      {modal && <div className="modal-backdrop" onMouseDown={() => setModal(null)}><div className="modal-card" onMouseDown={(event) => event.stopPropagation()}><div className="modal-head"><div><p className="eyebrow">НАСТРОЙКА</p><h2>{modal === "target" ? "Новый канал" : "Новый источник"}</h2></div><button className="icon-button" onClick={() => setModal(null)}><X size={18}/></button></div><p className="form-note"><span>*</span> обязательные поля</p>{modal === "target" ? <form noValidate onSubmit={(event) => void createTarget(event)} className="form-grid"><label>Название <b>*</b><input name="name" required minLength={1} placeholder="Новости 51 региона" /></label><label>Платформа <b>*</b><select name="platform" defaultValue="max" required><option value="max">MAX</option><option value="telegram">Telegram</option><option value="vk">VK</option></select></label><label>ID канала <b>*</b><input name="external_id" required minLength={1} placeholder="-77162942582085" /></label><label>Ссылка <small>необязательно</small><input name="url" type="url" placeholder="https://max.ru/..." /></label><button className="primary" disabled={busy}>Создать канал</button></form> : <form noValidate onSubmit={(event) => void createSource(event)} className="form-grid"><label>Название <b>*</b><input name="name" required minLength={1} placeholder="Полуостров 51" /></label><label>Платформа <b>*</b><select name="platform" defaultValue="vk" required><option value="vk">VK</option></select></label><label className="wide">Ссылка <b>*</b><input name="url" type="url" required placeholder="https://vk.com/peninsula51" /></label><button className="primary" disabled={busy}>Добавить источник</button></form>}</div></div>}
    </div>
  );
}
