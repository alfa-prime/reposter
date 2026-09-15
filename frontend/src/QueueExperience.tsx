import { ChangeEvent, useEffect, useMemo, useState } from "react";
import {
  Archive,
  X,
} from "lucide-react";
import { api, QueueItem, QueuePhoto, Target } from "./api";
import { QueueActionsFooter } from "./components/QueueActionsFooter";
import { QueueChannelFilter, QueueChannelOption } from "./components/QueueChannelFilter";
import { QueueDrawerHeader } from "./components/QueueDrawerHeader";
import { QueueMediaSection } from "./components/QueueMediaSection";
import { QueuePostCard } from "./components/QueuePostCard";
import { QueueSchedulePanel } from "./components/QueueSchedulePanel";
import { QueueTabs, QueueTab, queueTabConfig } from "./components/QueueTabs";
import { QueueTextEditor } from "./components/QueueTextEditor";
import { PostSignatureSection } from "./components/SignatureSections";
import "./queueExperience.css";
import "./queueLightTheme.css";

const QUEUE_TARGET_FILTER_KEY = "uncle-vlad-queue-target";

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

function initialQueueTargetFilter(): number | null {
  const saved = localStorage.getItem(QUEUE_TARGET_FILTER_KEY);
  if (!saved || saved === "all") return null;
  const targetId = Number(saved);
  return Number.isInteger(targetId) && targetId > 0 ? targetId : null;
}

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
  if (tab === "storage") return ["pending", "rewriting", "awaiting_moderation"].includes(status);
  if (tab === "publication") return ["approved", "scheduled"].includes(status);
  return ["published", "rejected", "failed"].includes(status);
}

function mediaKey(photo: QueuePhoto) {
  return photo.kind === "uploaded" && photo.media_id
    ? `uploaded:${photo.media_id}`
    : `source:${photo.attachment_id}`;
}

type QueueExperienceProps = {
  collectSignal?: number;
  targets?: Target[];
};

export function QueueExperience({ collectSignal = 0, targets = [] }: QueueExperienceProps) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tab, setTab] = useState<QueueTab>("storage");
  const [targetId, setTargetId] = useState<number | null>(initialQueueTargetFilter);
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

  const targetOptions = useMemo<QueueChannelOption[]>(() => {
    const knownTargets = new Map<number, QueueChannelOption>();
    for (const target of targets) knownTargets.set(target.target_id, { target_id: target.target_id, name: target.name });
    for (const item of items) {
      if (!knownTargets.has(item.target_id)) {
        knownTargets.set(item.target_id, {
          target_id: item.target_id,
          name: item.target_name ?? `Канал #${item.target_id}`,
        });
      }
    }
    return Array.from(knownTargets.values()).sort((a, b) => a.name.localeCompare(b.name, "ru"));
  }, [items, targets]);

  useEffect(() => {
    if (targetId !== null && !targetOptions.some((target) => target.target_id === targetId)) {
      setTargetId(null);
      localStorage.setItem(QUEUE_TARGET_FILTER_KEY, "all");
    }
  }, [targetId, targetOptions]);

  const scopedItems = useMemo(
    () => targetId === null ? items : items.filter((item) => item.target_id === targetId),
    [items, targetId],
  );

  const counts = useMemo(() => ({
    storage: scopedItems.filter((item) => statusMatchesTab(item.status, "storage")).length,
    publication: scopedItems.filter((item) => statusMatchesTab(item.status, "publication")).length,
    archive: scopedItems.filter((item) => statusMatchesTab(item.status, "archive")).length,
  }), [scopedItems]);

  const visibleItems = useMemo(
    () => scopedItems.filter((item) => statusMatchesTab(item.status, tab)),
    [scopedItems, tab],
  );

  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(""), 3500);
    return () => window.clearTimeout(timer);
  }, [message]);

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
    (async () => {
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

  function chooseTarget(nextTargetId: number | null) {
    setTargetId(nextTargetId);
    localStorage.setItem(QUEUE_TARGET_FILTER_KEY, nextTargetId === null ? "all" : String(nextTargetId));
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
    if (!selected || !scheduleAt) return;
    const updated = await runAction(
      () => api.schedule(selected.queue_item_id, new Date(scheduleAt).toISOString()),
      "Публикация запланирована",
    );
    if (updated) closeDrawer();
  }

  if (loading) return <div className="editorial-empty"><Archive size={32}/><strong>Загружаю очередь…</strong></div>;

  return (
    <div className="editorial-queue">
      {message && <div className="editorial-message"><span>{message}</span><button onClick={() => setMessage("")}><X size={18}/></button></div>}
      {error && <div className="editorial-message error"><span>{error}</span><button onClick={() => setError("")}><X size={18}/></button></div>}

      <div className="queue-toolbar">
        <QueueChannelFilter targets={targetOptions} value={targetId} onChange={chooseTarget} />
        <QueueTabs tab={tab} counts={counts} onChange={setTab} onRefresh={() => void loadQueue()} />
      </div>

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
            <strong>{queueTabConfig[tab].emptyTitle}</strong>
            <span>{queueTabConfig[tab].emptyText}</span>
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
              mediaOrder={mediaOrder}
              busy={busy}
              onMediaOrderChange={(next) => void saveMedia(next)}
              onLightbox={setLightbox}
              onUploadPhoto={uploadPhoto}
              onDeleteUploadedPhoto={(photo) => void deleteUploadedPhoto(photo)}
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

            {editing && (
              <div className="drawer-footer">
                <div className="drawer-main-actions">
                  <button className="primary" disabled={busy} onClick={() => void saveText()}>Сохранить текст</button>
                </div>
              </div>
            )}

            <PostSignatureSection
              item={selected}
              readonly={["published", "scheduled"].includes(selected.status)}
              onChanged={async () => {
                const updated = await api.queueItem(selected.queue_item_id);
                replaceItem(updated);
              }}
              onError={setError}
            />

            <QueueSchedulePanel value={scheduleAt} onChange={setScheduleAt} disabled={busy} visible={selected.status === "approved"} />

            <QueueActionsFooter
              item={selected}
              busy={busy}
              scheduleAt={scheduleAt}
              onSubmit={() => void runAction(() => api.submit(selected.queue_item_id))}
              onApprove={() => void runAction(() => api.approve(selected.queue_item_id))}
              onReject={() => void runAction(() => api.reject(selected.queue_item_id))}
              onReopen={() => void runAction(() => api.reopen(selected.queue_item_id))}
              onPublishNow={() => void publishNow()}
              onSchedule={() => void schedule()}
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
