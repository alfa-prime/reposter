import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ChevronRight,
  ExternalLink,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { api, QueueItem, Source, Target, TargetSource } from "./api";
import { AboutPage } from "./components/AboutPage";
import { Dashboard } from "./components/Dashboard";
import { Sidebar } from "./components/Sidebar";
import { SourcesPage } from "./components/SourcesPage";
import { TargetsPage } from "./components/TargetsPage";
import type { Section } from "./navigation";

type ConfirmDialog = {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
} | null;

const statusLabels: Record<string, string> = {
  pending: "В работе",
  rewriting: "Рерайт",
  awaiting_moderation: "На модерации",
  approved: "Одобрено",
  rejected: "Отклонено",
  scheduled: "Запланировано",
  published: "Опубликовано",
  failed: "Ошибка",
};

const activeQueueStatuses = new Set([
  "pending",
  "rewriting",
  "awaiting_moderation",
  "approved",
  "scheduled",
]);

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
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null);
  const [targetSources, setTargetSources] = useState<TargetSource[]>([]);
  const [draftText, setDraftText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog>(null);

  const activeTargets = useMemo(() => targets.filter((item) => item.is_active).length, [targets]);
  const activeSources = useMemo(() => sources.filter((item) => item.is_active).length, [sources]);
  const activeQueue = useMemo(() => queue.filter((item) => activeQueueStatuses.has(item.status)).length, [queue]);

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
        if (updatedTarget) {
          setTargetSources(await api.targetSources(updatedTarget.target_id));
        } else {
          setTargetSources([]);
        }
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

  function askDeleteTarget(target: Target) {
    setConfirmDialog({
      title: "Удалить канал?",
      message: `Канал «${target.name}» будет удалён вместе с его связями и очередью публикаций.`,
      confirmLabel: "Удалить канал",
      onConfirm: async () => {
        await api.deleteTarget(target.target_id);
        setSelectedTarget(null);
        setTargetSources([]);
        await loadAll();
        setNotice("Канал удалён");
      },
    });
  }

  function askDeleteSource(source: Source) {
    setConfirmDialog({
      title: "Удалить источник?",
      message: `Источник «${source.name}» будет удалён вместе с уже собранными из него постами и элементами очереди. Это действие нельзя отменить.`,
      confirmLabel: "Удалить источник",
      onConfirm: async () => {
        await api.deleteSource(source.source_id);
        await loadAll();
        setNotice("Источник удалён");
      },
    });
  }

  async function confirmAction() {
    if (!confirmDialog) return;
    const action = confirmDialog.onConfirm;
    setConfirmDialog(null);
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Операция не выполнена");
    } finally {
      setBusy(false);
    }
  }

  const pageTitle = section === "queue" ? "Редакционная очередь" : section === "targets" ? "Целевые каналы" : section === "sources" ? "Источники" : "Обзор";

  return (
    <div className="shell">
      <Sidebar section={section} onSectionChange={setSection} />

      <main className="workspace">
        {section !== "about" && <>
          <header className="topbar">
            <div><p className="eyebrow">ДЯДЯ ВЛАД · ЧИТАЕТ НОВОСТИ</p><h1>{pageTitle}</h1></div>
            <button className="primary" onClick={() => void collectNow()} disabled={busy}><RefreshCw size={17} className={busy ? "spin" : ""} />Собрать сейчас</button>
          </header>

          {(error || notice) && <div className={error ? "toast error" : "toast"}>{error || notice}<button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}
        </>}

        {section === "about" && <AboutPage />}

        {section === "dashboard" && <Dashboard
          activeTargets={activeTargets}
          totalTargets={targets.length}
          activeSources={activeSources}
          totalSources={sources.length}
          activeQueue={activeQueue}
          totalQueue={queue.length}
        />}

        {section === "queue" && <section className="queue-layout">
          <div className="queue-list">{queue.length === 0 && <div className="empty">Очередь пока пуста</div>}{queue.map((item) => <button key={item.queue_item_id} className={`queue-card ${selected?.queue_item_id === item.queue_item_id ? "selected" : ""}`} onClick={() => openItem(item)}><div className="queue-card-head"><span className={`badge status-${item.status}`}>{statusLabels[item.status] ?? item.status}</span><time>{shortDate(item.source_published_at)}</time></div><h3>{item.target_name ?? `Канал #${item.target_id}`}</h3><p>{item.original_text || "Пост без текста"}</p><div className="queue-card-bottom"><span>{item.photos.length ? `${item.photos.length} фото` : "без фото"}</span><ChevronRight size={16}/></div></button>)}</div>
          <div className="editor-panel">{!selected ? <div className="empty large"><Archive size={34}/><h3>Выберите пост</h3><p>Здесь появятся исходник, фотографии и редакционный текст.</p></div> : <><div className="editor-head"><div><span className={`badge status-${selected.status}`}>{statusLabels[selected.status] ?? selected.status}</span><h2>{selected.target_name ?? `Канал #${selected.target_id}`}</h2></div>{selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer">VK <ExternalLink size={14}/></a>}</div>{selected.photos.length > 0 && <div className="photo-strip">{selected.photos.map((photo) => <img key={photo.attachment_id} src={photo.source_url} alt="Вложение поста" />)}</div>}<div className="text-block"><label>Исходный текст</label><div className="original-text">{selected.original_text || "—"}</div></div><div className="text-block"><label>Текст для публикации</label><textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} rows={11} /></div><div className="actions"><button className="secondary" onClick={() => void runAction(() => api.updateQueueText(selected.queue_item_id, draftText), "Текст сохранён")}>Сохранить</button>{selected.status === "pending" && <button className="primary" onClick={() => void runAction(async () => { await api.updateQueueText(selected.queue_item_id, draftText); return api.submit(selected.queue_item_id); }, "Отправлено на модерацию")}>На модерацию</button>}{selected.status === "awaiting_moderation" && <><button className="danger" onClick={() => void runAction(() => api.reject(selected.queue_item_id), "Пост отклонён")}>Отклонить</button><button className="primary" onClick={() => void runAction(() => api.approve(selected.queue_item_id), "Пост одобрен")}>Одобрить</button></>}{["rejected", "approved", "scheduled", "awaiting_moderation"].includes(selected.status) && <button className="secondary" onClick={() => void runAction(() => api.reopen(selected.queue_item_id), "Пост возвращён в работу")}>Вернуть в работу</button>}</div></>}</div>
        </section>}

        {section === "targets" && <TargetsPage
          targets={targets}
          sources={sources}
          selectedTarget={selectedTarget}
          targetSources={targetSources}
          busy={busy}
          onOpenTarget={openTarget}
          onChanged={loadAll}
          onTargetSourcesChanged={setTargetSources}
          onDelete={askDeleteTarget}
          onError={setError}
          onNotice={setNotice}
        />}

        {section === "sources" && <SourcesPage
          sources={sources}
          busy={busy}
          onChanged={loadAll}
          onDelete={askDeleteSource}
          onError={setError}
          onNotice={setNotice}
        />}
      </main>

      {confirmDialog && <div className="modal-backdrop" onMouseDown={() => setConfirmDialog(null)}><div className="modal-card confirm-card" onMouseDown={(event) => event.stopPropagation()}><div className="modal-head"><div><p className="eyebrow">ПОДТВЕРЖДЕНИЕ</p><h2>{confirmDialog.title}</h2></div><button className="icon-button" onClick={() => setConfirmDialog(null)}><X size={18}/></button></div><p className="confirm-message">{confirmDialog.message}</p><div className="actions confirm-actions"><button className="secondary" onClick={() => setConfirmDialog(null)}>Отмена</button><button className="danger" disabled={busy} onClick={() => void confirmAction()}><Trash2 size={15}/>{confirmDialog.confirmLabel}</button></div></div></div>}
    </div>
  );
}
