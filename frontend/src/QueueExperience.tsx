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

function toLocalInput(value?: string | null) {
  const date = value ? new Date(value) : new Date(Date.now() + 15 * 60 * 1000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function mediaKey(photo: QueuePhoto) {
  return photo.kind === "uploaded" && photo.media_id
    ? `upload:${photo.media_id}`
    : `source:${photo.attachment_id}`;
}

function publicationErrorMessage(value?: string | null) {
  const raw = (value ?? "").trim();
  const normalized = raw.toLowerCase();
  if (
    normalized.includes("attachment.not.ready")
    || normalized.includes("file.not.processed")
    || normalized.includes("attachment.file.not.processed")
  ) {
    return "MAX не успел подготовить видео к отправке. Публикация не потеряна — попробуйте повторить её немного позже.";
  }
  if (normalized.includes("timeout") || normalized.includes("timed out")) {
    return "MAX слишком долго отвечал. Попробуйте повторить публикацию немного позже.";
  }
  if (normalized.includes("сертифик") || normalized.includes("ssl")) {
    return "Не удалось установить защищённое соединение с MAX. Повторите публикацию позже или обратитесь к администратору.";
  }
  return raw || "MAX не принял публикацию. Попробуйте повторить отправку позже.";
}

export function QueueExperience() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [tab, setTab] = useState<QueueTab>("storage");
  const [targetFilter, setTargetFilter] = useState<number | null>(initialQueueTargetFilter);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [scheduleAt, setScheduleAt] = useState("");
  const [lightbox, setLightbox] = useState<QueuePhoto | null>(null);
  const [mediaOrder, setMediaOrder] = useState<string[]>([]);

  const selected = useMemo(
    () => items.find((item) => item.queue_item_id === selectedId) ?? null,
    [items, selectedId],
  );

  const availableChannels = useMemo<QueueChannelOption[]>(() => {
    const channels = new Map<number, QueueChannelOption>();

    targets.forEach((target) => {
      channels.set(target.target_id, {
        target_id: target.target_id,
        name: target.name,
        is_active: target.is_active,
      });
    });

    items.forEach((item) => {
      if (!channels.has(item.target_id)) {
        channels.set(item.target_id, {
          target_id: item.target_id,
          name: item.target_name ?? `Канал #${item.target_id}`,
        });
      }
    });

    return Array.from(channels.values()).sort((a, b) => {
      if (a.is_active !== b.is_active) {
        if (a.is_active === false) return 1;
        if (b.is_active === false) return -1;
      }
      return a.name.localeCompare(b.name, "ru");
    });
  }, [items, targets]);

  const channelItems = useMemo(
    () => targetFilter === null ? items : items.filter((item) => item.target_id === targetFilter),
    [items, targetFilter],
  );

  const visibleItems = useMemo(
    () => channelItems.filter((item) => queueTabConfig[tab].statuses.includes(item.status)),
    [channelItems, tab],
  );

  const counts = useMemo(() => ({
    storage: channelItems.filter((item) => queueTabConfig.storage.statuses.includes(item.status)).length,
    scheduled: channelItems.filter((item) => queueTabConfig.scheduled.statuses.includes(item.status)).length,
    archive: channelItems.filter((item) => queueTabConfig.archive.statuses.includes(item.status)).length,
  }), [channelItems]);

  const orderedPhotos = useMemo(() => {
    if (!selected) return [];
    const index = new Map(mediaOrder.map((key, position) => [key, position]));
    return [...selected.photos].sort((a, b) => {
      const ai = index.get(mediaKey(a));
      const bi = index.get(mediaKey(b));
      if (ai !== undefined && bi !== undefined) return ai - bi;
      if (ai !== undefined) return -1;
      if (bi !== undefined) return 1;
      return a.position - b.position;
    });
  }, [selected, mediaOrder]);

  async function load(silent = false) {
    if (!silent) setBusy(true);
    try {
      const data = await api.queue();
      setItems(data);
      if (selectedId && !data.some((item) => item.queue_item_id === selectedId)) setSelectedId(null);
    } catch (exc) {
      if (!silent) setError(exc instanceof Error ? exc.message : "Не удалось загрузить очередь");
    } finally {
      if (!silent) setBusy(false);
    }
  }

  async function loadTargets(silent = false) {
    try {
      setTargets(await api.targets());
    } catch (exc) {
      if (!silent) setError(exc instanceof Error ? exc.message : "Не удалось загрузить список каналов");
    }
  }

  useEffect(() => {
    void load();
    void loadTargets();
    const timer = window.setInterval(() => void load(true), 8000);
    const onFocus = () => {
      void load(true);
      void loadTargets(true);
    };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  useEffect(() => {
    localStorage.setItem(QUEUE_TARGET_FILTER_KEY, targetFilter === null ? "all" : String(targetFilter));
  }, [targetFilter]);

  useEffect(() => {
    if (targetFilter === null || availableChannels.length === 0) return;
    if (!availableChannels.some((channel) => channel.target_id === targetFilter)) {
      setTargetFilter(null);
    }
  }, [availableChannels, targetFilter]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!selected) return;
    setDraft(selected.rewritten_text ?? selected.original_text ?? "");
    setScheduleAt(toLocalInput(selected.scheduled_at));
    setEditing(false);
    void api.queueMediaState(selected.queue_item_id)
      .then((state) => setMediaOrder(state.media_order))
      .catch(() => setMediaOrder(selected.photos.map(mediaKey)));
  }, [selectedId]);

  function applyUpdated(updated: QueueItem) {
    setItems((current) => current.map((item) => item.queue_item_id === updated.queue_item_id ? updated : item));
    setDraft(updated.rewritten_text ?? updated.original_text ?? "");
  }

  function applyQueueItemOnly(updated: QueueItem) {
    setItems((current) => current.map((item) => item.queue_item_id === updated.queue_item_id ? updated : item));
  }

  function changeTargetFilter(targetId: number | null) {
    setTargetFilter(targetId);
    setSelectedId(null);
  }

  async function action(run: () => Promise<QueueItem>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await run();
      applyUpdated(updated);
      setNotice(success);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Операция не выполнена");
    } finally {
      setBusy(false);
    }
  }

  async function saveMediaOrder(next: string[], success?: string) {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const state = await api.updateQueueMediaState(selected.queue_item_id, next);
      setMediaOrder(state.media_order);
      if (success) setNotice(success);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось изменить фотографии публикации");
    } finally {
      setBusy(false);
    }
  }

  async function togglePhoto(photo: QueuePhoto) {
    const key = mediaKey(photo);
    const included = mediaOrder.includes(key);
    const next = included ? mediaOrder.filter((item) => item !== key) : [...mediaOrder, key];
    await saveMediaOrder(next, included ? "Фото исключено из публикации" : "Фото добавлено в публикацию");
  }

  async function removeAllPhotos() {
    if (!selected || mediaOrder.length === 0) return;
    await saveMediaOrder([], "Все фото исключены из публикации");
  }

  async function restoreAllPhotos() {
    if (!selected) return;
    await saveMediaOrder(orderedPhotos.map(mediaKey), "Все фото возвращены в публикацию");
  }

  async function movePhoto(photo: QueuePhoto, direction: -1 | 1) {
    const key = mediaKey(photo);
    const current = mediaOrder.indexOf(key);
    const target = current + direction;
    if (current < 0 || target < 0 || target >= mediaOrder.length) return;
    const next = [...mediaOrder];
    [next[current], next[target]] = [next[target], next[current]];
    await saveMediaOrder(next);
  }

  async function saveText() {
    if (!selected) return;
    await action(() => api.updateQueueText(selected.queue_item_id, draft), "Текст сохранён");
    setEditing(false);
  }

  async function submit() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await api.updateQueueText(selected.queue_item_id, draft);
      const updated = await api.submit(selected.queue_item_id);
      applyUpdated(updated);
      setNotice("Пост отправлен на модерацию");
      setEditing(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось отправить на модерацию");
    } finally {
      setBusy(false);
    }
  }

  async function uploadPhotos(event: ChangeEvent<HTMLInputElement>) {
    if (!selected) return;
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    const invalid = files.find((file) => !["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024);
    if (invalid) {
      setError("Можно загружать JPEG, PNG или WebP до 10 МБ каждый");
      return;
    }

    setBusy(true);
    setError("");
    try {
      let updated = selected;
      for (const file of files) updated = await api.uploadQueuePhoto(selected.queue_item_id, file);
      applyUpdated(updated);
      const allKeys = updated.photos.map(mediaKey);
      const newKeys = allKeys.filter((key) => !selected.photos.some((photo) => mediaKey(photo) === key));
      const state = await api.updateQueueMediaState(selected.queue_item_id, [...mediaOrder, ...newKeys]);
      setMediaOrder(state.media_order);
      setNotice(files.length === 1 ? "Фото добавлено" : `Добавлено фото: ${files.length}`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить фото");
    } finally {
      setBusy(false);
    }
  }

  async function removeUploadedPhoto(photo: QueuePhoto) {
    if (!selected || !photo.media_id) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api.deleteQueuePhoto(selected.queue_item_id, photo.media_id);
      applyUpdated(updated);
      const key = mediaKey(photo);
      const state = await api.updateQueueMediaState(selected.queue_item_id, mediaOrder.filter((item) => item !== key));
      setMediaOrder(state.media_order);
      setNotice("Фото удалено");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось удалить фото");
    } finally {
      setBusy(false);
    }
  }

  async function schedule() {
    if (!selected || !scheduleAt) return;
    const date = new Date(scheduleAt);
    if (Number.isNaN(date.getTime())) {
      setError("Укажите корректную дату публикации");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await api.schedule(selected.queue_item_id, date.toISOString());
      applyUpdated(updated);
      setSelectedId(null);
      setTab("scheduled");
      setNotice("Публикация запланирована");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось поставить публикацию в очередь");
    } finally {
      setBusy(false);
    }
  }

  async function publishNow() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await api.publishNow(selected.queue_item_id);
      applyUpdated(updated);
      setSelectedId(null);
      setTab("archive");
      setNotice("Пост опубликован в MAX");
    } catch (exc) {
      setError(publicationErrorMessage(exc instanceof Error ? exc.message : null));
    } finally {
      setBusy(false);
    }
  }

  async function removeItem() {
    if (!selected || !window.confirm("Удалить эту публикацию из очереди?")) return;
    setBusy(true);
    try {
      await api.deleteQueueItem(selected.queue_item_id);
      setItems((current) => current.filter((item) => item.queue_item_id !== selected.queue_item_id));
      setSelectedId(null);
      setNotice("Публикация удалена");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось удалить публикацию");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="editorial-queue">
      <div className="queue-toolbar">
        <QueueChannelFilter
          channels={availableChannels}
          value={targetFilter}
          onChange={changeTargetFilter}
        />
        <QueueTabs
          tab={tab}
          counts={counts}
          busy={busy}
          onChange={(nextTab) => {
            setTab(nextTab);
            setSelectedId(null);
          }}
          onRefresh={() => {
            void load();
            void loadTargets(true);
          }}
        />
      </div>

      {(error || notice) && <div className={error ? "editorial-message error" : "editorial-message"}><span>{error || notice}</span><button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

      <div className="editorial-card-grid">
        {visibleItems.map((item) => (
          <QueuePostCard
            key={item.queue_item_id}
            item={item}
            statusLabel={statusLabels[item.status] ?? item.status}
            dateLabel={shortDate(item.source_published_at)}
            detailText={item.status === "failed" ? publicationErrorMessage(item.error_message) : item.original_text || "Пост без исходного текста"}
            onOpen={() => setSelectedId(item.queue_item_id)}
          />
        ))}
        {!visibleItems.length && (
          <div className="editorial-empty">
            <Archive size={30}/>
            <strong>Здесь пока пусто</strong>
            <span>{targetFilter === null ? "Посты появятся здесь по мере прохождения редакционного процесса." : "Для выбранного канала в этом разделе пока нет постов."}</span>
          </div>
        )}
      </div>

      {selected && (
        <div className="editorial-drawer-backdrop" onMouseDown={() => setSelectedId(null)}>
          <aside className="editorial-drawer" onMouseDown={(event) => event.stopPropagation()}>
            <QueueDrawerHeader
              item={selected}
              statusLabel={statusLabels[selected.status] ?? selected.status}
              scheduledLabel={selected.scheduled_at ? shortDate(selected.scheduled_at) : undefined}
              errorMessage={selected.status === "failed" ? publicationErrorMessage(selected.error_message) : undefined}
              onClose={() => setSelectedId(null)}
            />

            <QueueMediaSection
              item={selected}
              orderedPhotos={orderedPhotos}
              mediaOrder={mediaOrder}
              busy={busy}
              mediaKey={mediaKey}
              onRemoveAll={() => void removeAllPhotos()}
              onRestoreAll={() => void restoreAllPhotos()}
              onTogglePhoto={(photo) => void togglePhoto(photo)}
              onMovePhoto={(photo, direction) => void movePhoto(photo, direction)}
              onRemoveUploadedPhoto={(photo) => void removeUploadedPhoto(photo)}
              onOpenPhoto={setLightbox}
              onUploadPhotos={(event) => void uploadPhotos(event)}
              onError={(message) => {
                setNotice("");
                setError(message);
              }}
              onNotice={(message) => {
                setError("");
                setNotice(message);
              }}
            />

            <QueueTextEditor
              key={selected.queue_item_id}
              value={draft}
              originalText={selected.original_text}
              readonly={selected.status === "published"}
              editing={editing}
              onEditingChange={setEditing}
              onChange={setDraft}
            />

            <PostSignatureSection
              item={selected}
              onUpdated={applyQueueItemOnly}
              onError={(message) => {
                setNotice("");
                setError(message);
              }}
              onNotice={(message) => {
                setError("");
                setNotice(message);
              }}
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
              onSubmit={() => void submit()}
              onApprove={() => void action(() => api.approve(selected.queue_item_id), "Пост согласован")}
              onReject={() => void action(() => api.reject(selected.queue_item_id), "Пост отклонён")}
              onPublishNow={() => void publishNow()}
              onReopen={() => void action(() => api.reopen(selected.queue_item_id), "Пост возвращён в работу")}
              onDelete={() => void removeItem()}
            />
          </aside>
        </div>
      )}

      {lightbox && <div className="queue-lightbox" onClick={() => setLightbox(null)}><button onClick={() => setLightbox(null)}><X size={24}/></button><img src={lightbox.source_url} alt="Фото публикации" onClick={(event) => event.stopPropagation()}/></div>}
    </section>
  );
}
