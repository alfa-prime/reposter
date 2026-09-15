import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { Archive, X } from "lucide-react";
import { api, QueueItem, QueuePhoto } from "./api";
import { QueueActionsFooter } from "./components/QueueActionsFooter";
import { QueueDrawerHeader } from "./components/QueueDrawerHeader";
import { QueueMediaSection } from "./components/QueueMediaSection";
import { QueuePostCard } from "./components/QueuePostCard";
import { QueueSchedulePanel } from "./components/QueueSchedulePanel";
import { queueTabConfig, QueueTabs, QueueTab } from "./components/QueueTabs";
import { QueueTextEditor } from "./components/QueueTextEditor";
import { PostSignatureSection } from "./components/SignatureSections";
import "./queueExperience.css";
import "./queueLightTheme.css";

const statusLabels: Record<string, string> = {
  pending: "В работе",
  rewriting: "Рерайт",
  awaiting_moderation: "Требует модерации",
  approved: "Согласован",
  rejected: "Отклонён",
  scheduled: "Запланирован",
  published: "Опубликован",
  failed: "Ошибка публикации",
};

const emptyState: Record<QueueTab, { title: string; text: string }> = {
  storage: {
    title: "Хранилище пусто",
    text: "Новые собранные посты появятся здесь.",
  },
  moderation: {
    title: "Нет постов на модерации",
    text: "Публикации, подготовленные редактором, появятся здесь.",
  },
  scheduled: {
    title: "Очередь публикаций пуста",
    text: "Согласованные и запланированные публикации появятся здесь.",
  },
  archive: {
    title: "Архив пуст",
    text: "Опубликованные, отклонённые и неудачные публикации появятся здесь.",
  },
};

function shortDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function scheduleLabel(value?: string | null) {
  if (!value) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusMatchesTab(status: string, tab: QueueTab) {
  return queueTabConfig[tab].statuses.includes(status);
}

function mediaKey(photo: QueuePhoto) {
  return photo.kind === "uploaded" && photo.media_id
    ? `uploaded:${photo.media_id}`
    : `source:${photo.attachment_id}`;
}

type QueueExperienceProps = {
  collectSignal?: number;
  targetId: number | null;
};

export function QueueExperience({ collectSignal = 0, targetId }: QueueExperienceProps) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tab, setTab] = useState<QueueTab>("storage");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [rewriteBusy, setRewriteBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);
  const [mediaOrder, setMediaOrder] = useState<string[]>([]);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [scheduleAt, setScheduleAt] = useState("");

  const selected = useMemo(
    () => items.find((item) => item.queue_item_id === selectedId) ?? null,
    [items, selectedId],
  );

  const scopedItems = useMemo(
    () => targetId === null ? items : items.filter((item) => item.target_id === targetId),
    [items, targetId],
  );

  const counts = useMemo<Record<QueueTab, number>>(() => ({
    storage: scopedItems.filter((item) => statusMatchesTab(item.status, "storage")).length,
    moderation: scopedItems.filter((item) => statusMatchesTab(item.status, "moderation")).length,
    scheduled: scopedItems.filter((item) => statusMatchesTab(item.status, "scheduled")).length,
    archive: scopedItems.filter((item) => statusMatchesTab(item.status, "archive")).length,
  }), [scopedItems]);

  const visibleItems = useMemo(
    () => scopedItems.filter((item) => statusMatchesTab(item.status, tab)),
    [scopedItems, tab],
  );

  const orderedPhotos = useMemo(() => {
    if (!selected) return [];
    const byKey = new Map(selected.photos.map((photo) => [mediaKey(photo), photo]));
    const included = mediaOrder
      .map((key) => byKey.get(key))
      .filter((photo): photo is QueuePhoto => Boolean(photo));
    const includedKeys = new Set(mediaOrder);
    const excluded = selected.photos.filter((photo) => !includedKeys.has(mediaKey(photo)));
    return [...included, ...excluded];
  }, [selected, mediaOrder]);

  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(""), 3500);
    return () => window.clearTimeout(timer);
  }, [message]);

  useEffect(() => {
    if (selected && targetId !== null && selected.target_id !== targetId) closeDrawer();
  }, [targetId]);

  async function loadQueue() {
    try {
      const queue = await api.queue();
      setItems(queue);
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить очередь");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadQueue();
  }, [collectSignal]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    void (async () => {
      try {
        const item = await api.queueItem(selectedId);
        const state = await api.queueMediaState(selectedId);
        if (!active) return;
        setItems((current) => current.map((row) => row.queue_item_id === item.queue_item_id ? item : row));
        setText(item.rewritten_text ?? item.original_text ?? "");
        setMediaOrder(state.media_order);
        setScheduleAt(item.scheduled_at ? item.scheduled_at.slice(0, 16) : "");
        setEditing(false);
        setError("");
      } catch (exc) {
        if (active) setError(exc instanceof Error ? exc.message : "Не удалось открыть публикацию");
      }
    })();
    return () => { active = false; };
  }, [selectedId]);

  function replaceItem(updated: QueueItem) {
    setItems((current) => current.map((item) => item.queue_item_id === updated.queue_item_id ? updated : item));
  }

  function closeDrawer() {
    setSelectedId(null);
    setEditing(false);
    setLightbox(null);
  }

  async function runAction(action: () => Promise<QueueItem>, successMessage = "") {
    setBusy(true);
    setError("");
    try {
      const updated = await action();
      replaceItem(updated);
      setText(updated.rewritten_text ?? updated.original_text ?? "");
      if (successMessage) setMessage(successMessage);
      return updated;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Операция не выполнена");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function rewrite() {
    if (!selected) return;
    setRewriteBusy(true);
    setError("");
    try {
      const updated = await api.rewriteQueueItem(selected.queue_item_id);
      replaceItem(updated);
      setText(updated.rewritten_text ?? updated.original_text ?? "");
      setEditing(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось переписать публикацию");
    } finally {
      setRewriteBusy(false);
    }
  }

  async function saveText() {
    if (!selected) return;
    const updated = await runAction(() => api.updateQueueText(selected.queue_item_id, text));
    if (updated) setEditing(false);
  }

  async function submitForModeration() {
    if (!selected) return;

    const preparedText = text.trim();
    if (!preparedText) {
      setError("Перед отправкой на модерацию нужен текст публикации");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const savedText = selected.rewritten_text ?? "";
      if (savedText !== text || !savedText.trim()) {
        const saved = await api.updateQueueText(selected.queue_item_id, text);
        replaceItem(saved);
      }

      const updated = await api.submit(selected.queue_item_id);
      replaceItem(updated);
      closeDrawer();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось отправить публикацию на модерацию");
    } finally {
      setBusy(false);
    }
  }

  async function saveMedia(nextOrder: string[]) {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const state = await api.updateQueueMediaState(selected.queue_item_id, nextOrder);
      setMediaOrder(state.media_order);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось изменить медиа");
    } finally {
      setBusy(false);
    }
  }

  function togglePhoto(photo: QueuePhoto) {
    const key = mediaKey(photo);
    const next = mediaOrder.includes(key)
      ? mediaOrder.filter((item) => item !== key)
      : [...mediaOrder, key];
    void saveMedia(next);
  }

  function movePhoto(photo: QueuePhoto, direction: -1 | 1) {
    const key = mediaKey(photo);
    const index = mediaOrder.indexOf(key);
    const targetIndex = index + direction;
    if (index < 0 || targetIndex < 0 || targetIndex >= mediaOrder.length) return;
    const next = [...mediaOrder];
    [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
    void saveMedia(next);
  }

  async function uploadPhoto(event: ChangeEvent<HTMLInputElement>) {
    if (!selected || !event.target.files?.length) return;
    const files = Array.from(event.target.files);
    setBusy(true);
    setError("");
    try {
      let updated = selected;
      for (const file of files) updated = await api.uploadQueuePhoto(selected.queue_item_id, file);
      replaceItem(updated);
      const state = await api.queueMediaState(selected.queue_item_id);
      setMediaOrder(state.media_order);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить фото");
    } finally {
      event.target.value = "";
      setBusy(false);
    }
  }

  async function deleteUploadedPhoto(photo: QueuePhoto) {
    if (!selected || !photo.media_id) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api.deleteQueuePhoto(selected.queue_item_id, photo.media_id);
      replaceItem(updated);
      const state = await api.queueMediaState(selected.queue_item_id);
      setMediaOrder(state.media_order);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось удалить фото");
    } finally {
      setBusy(false);
    }
  }

  async function deleteItem() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteQueueItem(selected.queue_item_id);
      setItems((current) => current.filter((item) => item.queue_item_id !== selected.queue_item_id));
      closeDrawer();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось удалить публикацию");
    } finally {
      setBusy(false);
    }
  }

  async function publishNow() {
    if (!selected) return;
    const updated = await runAction(
      () => api.publishNow(selected.queue_item_id),
      "Публикация отправлена",
    );
    if (updated) closeDrawer();
  }

  async function schedule() {
    if (!selected) return;

    if (!scheduleAt) {
      setError("Укажите дату и время публикации");
      return;
    }

    const scheduledDate = new Date(scheduleAt);
    if (Number.isNaN(scheduledDate.getTime())) {
      setError("Укажите корректную дату и время публикации");
      return;
    }

    if (scheduledDate.getTime() <= Date.now()) {
      setError("Дата и время публикации должны быть в будущем");
      return;
    }

    const updated = await runAction(
      () => api.schedule(selected.queue_item_id, scheduledDate.toISOString()),
      "Публикация запланирована",
    );
    if (updated) closeDrawer();
  }

  if (loading) {
    return <div className="editorial-empty"><Archive size={32}/><strong>Загружаю очередь…</strong></div>;
  }

  return (
    <div className="editorial-queue">
      {message && <div className="editorial-message"><span>{message}</span><button onClick={() => setMessage("")}><X size={18}/></button></div>}
      {error && <div className="editorial-message error"><span>{error}</span><button onClick={() => setError("")}><X size={18}/></button></div>}

      <QueueTabs tab={tab} counts={counts} busy={busy} onChange={setTab} onRefresh={() => void loadQueue()} />

      <div className="editorial-card-grid">
        {visibleItems.map((item) => (
          <QueuePostCard
            key={item.queue_item_id}
            item={item}
            statusLabel={statusLabels[item.status] ?? item.status}
            dateLabel={shortDate(item.source_published_at)}
            detailText={(item.original_text ?? "").slice(0, 180)}
            onOpen={() => setSelectedId(item.queue_item_id)}
          />
        ))}
        {visibleItems.length === 0 && (
          <div className="editorial-empty">
            <Archive size={34}/>
            <strong>{emptyState[tab].title}</strong>
            <span>{emptyState[tab].text}</span>
          </div>
        )}
      </div>

      {selected && (
        <div className="editorial-drawer-backdrop" onMouseDown={closeDrawer}>
          <aside className="editorial-drawer" onMouseDown={(event) => event.stopPropagation()}>
            <QueueDrawerHeader
              item={selected}
              statusLabel={statusLabels[selected.status] ?? selected.status}
              scheduledLabel={scheduleLabel(selected.scheduled_at)}
              errorMessage={selected.error_message ?? undefined}
              onClose={closeDrawer}
            />

            <QueueMediaSection
              item={selected}
              orderedPhotos={orderedPhotos}
              mediaOrder={mediaOrder}
              busy={busy}
              mediaKey={mediaKey}
              onRemoveAll={() => void saveMedia([])}
              onRestoreAll={() => void saveMedia(selected.photos.map(mediaKey))}
              onTogglePhoto={togglePhoto}
              onMovePhoto={movePhoto}
              onRemoveUploadedPhoto={(photo) => void deleteUploadedPhoto(photo)}
              onOpenPhoto={(photo) => setLightbox(photo.source_url)}
              onUploadPhotos={uploadPhoto}
              onError={setError}
              onNotice={setMessage}
            />

            <QueueTextEditor
              value={text}
              originalText={selected.original_text}
              readonly={["published", "scheduled"].includes(selected.status)}
              editing={editing}
              busy={busy}
              rewriteBusy={rewriteBusy}
              canRewrite={["pending", "rewriting", "rejected"].includes(selected.status)}
              onEditingChange={setEditing}
              onChange={setText}
              onRewrite={() => void rewrite()}
            />

            <PostSignatureSection
              item={selected}
              onUpdated={replaceItem}
              onError={setError}
            />

            {selected.status === "approved" && (
              <QueueSchedulePanel
                value={scheduleAt}
                busy={busy}
                onChange={setScheduleAt}
                onSchedule={() => void schedule()}
              />
            )}

            <QueueActionsFooter
              item={selected}
              editing={editing}
              busy={busy}
              onSaveText={() => void saveText()}
              onSubmit={() => void submitForModeration()}
              onApprove={() => void runAction(() => api.approve(selected.queue_item_id))}
              onReject={() => void runAction(() => api.reject(selected.queue_item_id))}
              onReopen={() => void runAction(() => api.reopen(selected.queue_item_id))}
              onPublishNow={() => void publishNow()}
              onDelete={() => void deleteItem()}
            />
          </aside>
        </div>
      )}

      {lightbox && (
        <div className="queue-lightbox" onClick={() => setLightbox(null)}>
          <img src={lightbox} alt="" onClick={(event) => event.stopPropagation()} />
          <button onClick={() => setLightbox(null)}><X size={22}/></button>
        </div>
      )}
    </div>
  );
}
