import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  ArrowLeft,
  ArrowRight,
  Bold,
  CalendarClock,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Eye,
  EyeOff,
  FileImage,
  Inbox,
  Italic,
  Link as LinkIcon,
  Pencil,
  RefreshCw,
  RotateCcw,
  Send,
  Smile,
  Strikethrough,
  Trash2,
  Underline,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import { api, QueueItem, QueuePhoto } from "./api";
import "./queueExperience.css";

type QueueTab = "storage" | "scheduled" | "archive";

type LinkSelection = {
  start: number;
  end: number;
};

const statusLabels: Record<string, string> = {
  pending: "В работе",
  rewriting: "Рерайт",
  awaiting_moderation: "Требует модерации",
  approved: "Согласован",
  rejected: "Отклонён",
  scheduled: "Запланирован",
  failed: "Ошибка",
};

const tabConfig: Record<QueueTab, { label: string; statuses: string[] }> = {
  storage: { label: "Хранилище постов", statuses: ["pending", "rewriting", "awaiting_moderation"] },
  scheduled: { label: "Очередь публикаций", statuses: ["approved", "scheduled"] },
  archive: { label: "Архив", statuses: ["rejected", "failed"] },
};

const emojis = ["😀", "🙂", "😉", "😍", "🔥", "✨", "👍", "👏", "❤️", "📌", "📣", "⚡", "❗", "✅", "➡️", "🎉", "📷", "🚀"];

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

function normalizeUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

export function QueueExperience() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [tab, setTab] = useState<QueueTab>("storage");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [scheduleAt, setScheduleAt] = useState("");
  const [lightbox, setLightbox] = useState<QueuePhoto | null>(null);
  const [mediaOrder, setMediaOrder] = useState<string[]>([]);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [linkText, setLinkText] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkError, setLinkError] = useState("");
  const [linkSelection, setLinkSelection] = useState<LinkSelection>({ start: 0, end: 0 });
  const textRef = useRef<HTMLTextAreaElement | null>(null);
  const linkTextRef = useRef<HTMLInputElement | null>(null);

  const selected = useMemo(
    () => items.find((item) => item.queue_item_id === selectedId) ?? null,
    [items, selectedId],
  );

  const visibleItems = useMemo(
    () => items.filter((item) => tabConfig[tab].statuses.includes(item.status)),
    [items, tab],
  );

  const counts = useMemo(() => ({
    storage: items.filter((item) => tabConfig.storage.statuses.includes(item.status)).length,
    scheduled: items.filter((item) => tabConfig.scheduled.statuses.includes(item.status)).length,
    archive: items.filter((item) => tabConfig.archive.statuses.includes(item.status)).length,
  }), [items]);

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

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(true), 8000);
    const onFocus = () => void load(true);
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    setDraft(selected.rewritten_text ?? selected.original_text ?? "");
    setScheduleAt(toLocalInput(selected.scheduled_at));
    setEditing(false);
    setShowSource(false);
    setEmojiOpen(false);
    setLinkDialogOpen(false);
    void api.queueMediaState(selected.queue_item_id)
      .then((state) => setMediaOrder(state.media_order))
      .catch(() => setMediaOrder(selected.photos.map(mediaKey)));
  }, [selectedId]);

  useEffect(() => {
    if (!linkDialogOpen) return;
    requestAnimationFrame(() => linkTextRef.current?.focus());
  }, [linkDialogOpen]);

  function applyUpdated(updated: QueueItem) {
    setItems((current) => current.map((item) => item.queue_item_id === updated.queue_item_id ? updated : item));
    setDraft(updated.rewritten_text ?? updated.original_text ?? "");
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

  function replaceSelection(prefix: string, suffix = prefix, placeholder = "текст") {
    const textarea = textRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = draft.slice(start, end) || placeholder;
    const next = `${draft.slice(0, start)}${prefix}${selectedText}${suffix}${draft.slice(end)}`;
    setDraft(next);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selectedText.length);
    });
  }

  function insertAtCursor(value: string) {
    const textarea = textRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    setDraft(`${draft.slice(0, start)}${value}${draft.slice(end)}`);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + value.length, start + value.length);
    });
  }

  function openLinkDialog() {
    const textarea = textRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    setLinkSelection({ start, end });
    setLinkText(draft.slice(start, end));
    setLinkUrl("");
    setLinkError("");
    setEmojiOpen(false);
    setLinkDialogOpen(true);
  }

  function closeLinkDialog() {
    setLinkDialogOpen(false);
    setLinkError("");
    requestAnimationFrame(() => textRef.current?.focus());
  }

  function confirmLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const label = linkText.trim();
    const url = normalizeUrl(linkUrl);
    if (!label) {
      setLinkError("Укажите текст ссылки");
      return;
    }
    if (!url) {
      setLinkError("Укажите адрес ссылки");
      return;
    }

    const value = `[${label}](${url})`;
    const { start, end } = linkSelection;
    setDraft(`${draft.slice(0, start)}${value}${draft.slice(end)}`);
    setLinkDialogOpen(false);
    setLinkError("");
    requestAnimationFrame(() => {
      const textarea = textRef.current;
      textarea?.focus();
      textarea?.setSelectionRange(start + value.length, start + value.length);
    });
  }

  async function schedule() {
    if (!selected || !scheduleAt) return;
    const date = new Date(scheduleAt);
    if (Number.isNaN(date.getTime())) {
      setError("Укажите корректную дату публикации");
      return;
    }
    await action(() => api.schedule(selected.queue_item_id, date.toISOString()), "Публикация запланирована");
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
      <div className="editorial-tabs" role="tablist" aria-label="Разделы очереди">
        {(Object.keys(tabConfig) as QueueTab[]).map((key) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => { setTab(key); setSelectedId(null); }} role="tab">
            {key === "storage" ? <Inbox size={17}/> : key === "scheduled" ? <Clock3 size={17}/> : <Archive size={17}/>} 
            <span>{tabConfig[key].label}</span><b>{counts[key]}</b>
          </button>
        ))}
        <button className="editorial-refresh" onClick={() => void load()} disabled={busy} title="Обновить"><RefreshCw size={17} className={busy ? "spin" : ""}/></button>
      </div>

      {(error || notice) && <div className={error ? "editorial-message error" : "editorial-message"}><span>{error || notice}</span><button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

      <div className="editorial-card-grid">
        {visibleItems.map((item) => (
          <button className="editorial-post-card" key={item.queue_item_id} onClick={() => setSelectedId(item.queue_item_id)}>
            {item.photos[0] && <img src={item.photos[0].source_url} alt=""/>}
            <div className="editorial-card-body">
              <div className="editorial-card-meta"><span>{item.target_name ?? `Канал #${item.target_id}`}</span><time>{shortDate(item.source_published_at)}</time></div>
              <strong>{(item.rewritten_text ?? item.original_text ?? "Пост без текста").slice(0, 120)}</strong>
              <p>{item.original_text || "Пост без исходного текста"}</p>
              <div className={`editorial-status status-${item.status}`}>{statusLabels[item.status] ?? item.status}</div>
            </div>
          </button>
        ))}
        {!visibleItems.length && <div className="editorial-empty"><Archive size={30}/><strong>Здесь пока пусто</strong><span>Посты появятся здесь по мере прохождения редакционного процесса.</span></div>}
      </div>

      {selected && (
        <div className="editorial-drawer-backdrop" onMouseDown={() => setSelectedId(null)}>
          <aside className="editorial-drawer" onMouseDown={(event) => event.stopPropagation()}>
            <header className="editorial-drawer-head">
              <button className="drawer-close" onClick={() => setSelectedId(null)}><X size={22}/></button>
              <div><h2>{selected.status === "scheduled" ? "Публикация в очереди" : "Публикация на модерации"}</h2><div className={`editorial-status status-${selected.status}`}>{statusLabels[selected.status] ?? selected.status}</div></div>
            </header>

            {selected.status === "scheduled" && selected.scheduled_at && <div className="scheduled-banner"><CalendarClock size={18}/> Запланировано на {shortDate(selected.scheduled_at)}</div>}

            <div className="drawer-source-row">
              <div><strong>{selected.target_name ?? `Канал #${selected.target_id}`}</strong><span>Источник публикации</span></div>
              {selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer">Перейти к посту <ExternalLink size={14}/></a>}
            </div>

            <div className="drawer-media">
              <div className="drawer-section-title media-section-title">
                <span>Медиа публикации</span>
                <div className="media-summary-actions">
                  <span>В публикации {mediaOrder.length} из {selected.photos.length}</span>
                  {selected.photos.length > 0 && (
                    <div className="media-bulk-actions">
                      <button type="button" onClick={() => void removeAllPhotos()} disabled={busy || mediaOrder.length === 0}>Убрать все</button>
                      <button type="button" onClick={() => void restoreAllPhotos()} disabled={busy || mediaOrder.length === selected.photos.length}>Вернуть все</button>
                    </div>
                  )}
                </div>
              </div>
              {selected.photos.length > 0 ? (
                <div className="drawer-photo-grid">
                  {orderedPhotos.map((photo) => {
                    const key = mediaKey(photo);
                    const included = mediaOrder.includes(key);
                    const orderIndex = mediaOrder.indexOf(key);
                    return (
                      <div className={`drawer-photo ${included ? "included" : "excluded"}`} key={key}>
                        <img src={photo.source_url} alt="Фото публикации" onClick={() => setLightbox(photo)}/>
                        {!included && <div className="media-excluded-label">Не попадёт в публикацию</div>}
                        <div className="media-controls media-controls-readable">
                          <button className={included ? "media-remove" : "media-restore"} title={included ? "Убрать фото из публикации" : "Вернуть фото в публикацию"} onClick={() => void togglePhoto(photo)}>
                            {included ? <EyeOff size={14}/> : <Eye size={14}/>}<span>{included ? "Убрать" : "Вернуть"}</span>
                          </button>
                          {included && <button title="Сдвинуть левее" disabled={orderIndex <= 0} onClick={() => void movePhoto(photo, -1)}><ArrowLeft size={14}/></button>}
                          {included && <button title="Сдвинуть правее" disabled={orderIndex < 0 || orderIndex >= mediaOrder.length - 1} onClick={() => void movePhoto(photo, 1)}><ArrowRight size={14}/></button>}
                          {photo.kind === "uploaded" && photo.media_id && <button className="media-delete-file" title="Удалить загруженный файл" onClick={() => void removeUploadedPhoto(photo)}><Trash2 size={14}/><span>Удалить файл</span></button>}
                        </div>
                        <span>{photo.kind === "uploaded" ? "Добавлено вручную" : included ? `№ ${orderIndex + 1}` : "Исключено"}</span>
                      </div>
                    );
                  })}
                </div>
              ) : <div className="no-media"><FileImage size={28}/><span>У публикации пока нет фотографий</span></div>}

              <label className="upload-media-button"><Upload size={17}/>Добавить фото<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => void uploadPhotos(event)} disabled={busy}/></label>
              <small>«Убрать» исключает исходное фото только из публикации — сам оригинал остаётся. Загруженные вручную файлы можно удалить полностью · JPEG, PNG или WebP · до 10 МБ на файл.</small>
            </div>

            <div className="drawer-text-section">
              <div className="drawer-section-title"><span>Текст поста</span><span>{draft.length} знаков</span></div>

              {editing ? (
                <div className="rich-editor">
                  <div className="rich-toolbar" aria-label="Форматирование текста">
                    <button type="button" title="Жирный" onClick={() => replaceSelection("**")}><Bold size={17}/></button>
                    <button type="button" title="Курсив" onClick={() => replaceSelection("_")}><Italic size={17}/></button>
                    <button type="button" title="Зачёркнутый" onClick={() => replaceSelection("~~")}><Strikethrough size={17}/></button>
                    <button type="button" title="Подчёркнутый" onClick={() => replaceSelection("<u>", "</u>")}><Underline size={17}/></button>
                    <span className="toolbar-divider"/>
                    <button type="button" title="Вставить ссылку" onClick={openLinkDialog}><LinkIcon size={17}/></button>
                    <div className="emoji-control">
                      <button type="button" title="Эмодзи" onClick={() => setEmojiOpen((value) => !value)}><Smile size={18}/></button>
                      {emojiOpen && <div className="emoji-picker">{emojis.map((emoji) => <button type="button" key={emoji} onClick={() => { insertAtCursor(emoji); setEmojiOpen(false); }}>{emoji}</button>)}</div>}
                    </div>
                  </div>
                  <textarea ref={textRef} value={draft} onChange={(event) => setDraft(event.target.value)} rows={12} autoFocus/>
                  <small className="format-hint">Поддерживается редакторская разметка: жирный, курсив, зачёркивание, подчёркивание, ссылки и эмодзи.</small>
                </div>
              ) : <div className="publication-text">{draft || "—"}</div>}

              <div className="drawer-inline-actions">
                <button onClick={() => setEditing((value) => !value)}><Pencil size={16}/>{editing ? "Закончить редактирование" : "Редактировать"}</button>
                <button onClick={() => setShowSource((value) => !value)}>{showSource ? "Скрыть исходник" : "Показать текст источника"}</button>
              </div>
              {showSource && <div className="source-text-preview">{selected.original_text || "—"}</div>}
            </div>

            {selected.status === "approved" && <div className="schedule-panel"><label>Дата и время публикации<input type="datetime-local" value={scheduleAt} onChange={(event) => setScheduleAt(event.target.value)}/></label><button className="primary" onClick={() => void schedule()} disabled={busy}><CalendarClock size={17}/>Поставить в очередь</button></div>}

            <footer className="drawer-footer">
              <div className="drawer-main-actions">
                {editing && <button className="secondary" onClick={() => void saveText()} disabled={busy}>Сохранить текст</button>}
                {["pending", "rewriting", "rejected"].includes(selected.status) && <button className="primary" onClick={() => void submit()} disabled={busy}><Send size={17}/>На модерацию</button>}
                {selected.status === "awaiting_moderation" && <><button className="primary" onClick={() => void action(() => api.approve(selected.queue_item_id), "Пост согласован")} disabled={busy}><CheckCircle2 size={17}/>Согласовать пост</button><button className="danger" onClick={() => void action(() => api.reject(selected.queue_item_id), "Пост отклонён")} disabled={busy}><XCircle size={17}/>Отклонить</button></>}
                {["approved", "scheduled", "rejected"].includes(selected.status) && <button className="secondary" onClick={() => void action(() => api.reopen(selected.queue_item_id), "Пост возвращён в работу")} disabled={busy}><RotateCcw size={17}/>Вернуть в работу</button>}
              </div>
              <button className="drawer-delete" onClick={() => void removeItem()} disabled={busy}><Trash2 size={16}/>Удалить</button>
            </footer>
          </aside>
        </div>
      )}

      {linkDialogOpen && (
        <div className="link-dialog-backdrop" onMouseDown={closeLinkDialog}>
          <form className="link-dialog" onSubmit={confirmLink} onMouseDown={(event) => event.stopPropagation()}>
            <div className="link-dialog-head">
              <div>
                <h3>Вставить ссылку</h3>
                <p>Укажите, какой текст увидит читатель, и адрес страницы.</p>
              </div>
              <button type="button" className="link-dialog-close" onClick={closeLinkDialog} aria-label="Закрыть"><X size={19}/></button>
            </div>
            <label>
              <span>Текст ссылки</span>
              <input ref={linkTextRef} value={linkText} onChange={(event) => { setLinkText(event.target.value); setLinkError(""); }} placeholder="Например: Подробнее на сайте" />
            </label>
            <label>
              <span>Адрес ссылки</span>
              <input value={linkUrl} onChange={(event) => { setLinkUrl(event.target.value); setLinkError(""); }} placeholder="https://example.com" inputMode="url" />
            </label>
            {linkError && <div className="link-dialog-error">{linkError}</div>}
            <div className="link-dialog-actions">
              <button type="button" className="secondary" onClick={closeLinkDialog}>Отмена</button>
              <button type="submit" className="primary"><LinkIcon size={16}/>Вставить ссылку</button>
            </div>
          </form>
        </div>
      )}

      {lightbox && <div className="queue-lightbox" onClick={() => setLightbox(null)}><button onClick={() => setLightbox(null)}><X size={24}/></button><img src={lightbox.source_url} alt="Фото публикации" onClick={(event) => event.stopPropagation()}/></div>}
    </section>
  );
}
