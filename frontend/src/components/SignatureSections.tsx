import { FormEvent, useEffect, useRef, useState } from "react";
import { Bold, Italic, Link as LinkIcon, Save, Smile, Underline } from "lucide-react";
import { api, QueueItem, Target } from "../api";
import "../signatures.css";

const emojis = ["📣", "👉", "✅", "❤️", "🔥", "✨", "📌", "➡️", "🙂", "👍"];

function normalizeUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

type MiniSignatureEditorProps = {
  value: string;
  onSave: (value: string) => Promise<void>;
  inherited?: boolean;
  onReset?: () => Promise<void>;
  onError?: (message: string) => void;
};

function MiniSignatureEditor({ value, onSave, inherited, onReset, onError }: MiniSignatureEditorProps) {
  const [draft, setDraft] = useState(value);
  const [busy, setBusy] = useState(false);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkText, setLinkText] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => setDraft(value), [value]);

  function wrap(prefix: string, suffix = prefix) {
    const area = ref.current;
    if (!area) return;
    const start = area.selectionStart;
    const end = area.selectionEnd;
    const selected = draft.slice(start, end) || "текст";
    setDraft(`${draft.slice(0, start)}${prefix}${selected}${suffix}${draft.slice(end)}`);
    requestAnimationFrame(() => area.focus());
  }

  function insert(value: string) {
    const area = ref.current;
    if (!area) return;
    const start = area.selectionStart;
    const end = area.selectionEnd;
    const caret = start + value.length;
    setDraft(`${draft.slice(0, start)}${value}${draft.slice(end)}`);
    requestAnimationFrame(() => {
      area.focus();
      area.setSelectionRange(caret, caret);
    });
  }

  function openLink() {
    const area = ref.current;
    if (!area) return;
    setSelection({ start: area.selectionStart, end: area.selectionEnd });
    setLinkText(draft.slice(area.selectionStart, area.selectionEnd));
    setLinkUrl("");
    setLinkOpen(true);
  }

  function submitLink(event: FormEvent) {
    event.preventDefault();
    const text = linkText.trim();
    const url = normalizeUrl(linkUrl);
    if (!text || !url) return;
    const token = `[${text}](${url})`;
    setDraft(`${draft.slice(0, selection.start)}${token}${draft.slice(selection.end)}`);
    setLinkOpen(false);
  }

  async function run(operation: () => Promise<void>) {
    setBusy(true);
    try {
      await operation();
    } catch (exc) {
      onError?.(exc instanceof Error ? exc.message : "Не удалось сохранить подпись");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="signature-editor">
      {inherited && <div className="signature-inherited">Сейчас используется подпись канала по умолчанию</div>}
      <div className="signature-toolbar">
        <button type="button" title="Жирный" onClick={() => wrap("**")}><Bold size={15} /></button>
        <button type="button" title="Курсив" onClick={() => wrap("_")}><Italic size={15} /></button>
        <button type="button" title="Подчёркнутый" onClick={() => wrap("<u>", "</u>")}><Underline size={15} /></button>
        <button type="button" title="Ссылка" onClick={openLink}><LinkIcon size={15} /></button>
        <div className="signature-emoji-wrap">
          <button type="button" title="Эмодзи" onClick={() => setEmojiOpen((value) => !value)}><Smile size={16} /></button>
          {emojiOpen && (
            <div className="signature-emoji">
              {emojis.map((emoji) => (
                <button type="button" key={emoji} onClick={() => { insert(emoji); setEmojiOpen(false); }}>{emoji}</button>
              ))}
            </div>
          )}
        </div>
      </div>
      <textarea ref={ref} value={draft} onChange={(event) => setDraft(event.target.value)} rows={4} placeholder="Например: 📣 Подписывайтесь на наш канал" />
      <div className="signature-actions">
        {onReset && !inherited && (
          <button type="button" className="signature-secondary" disabled={busy} onClick={() => void run(onReset)}>
            Вернуть подпись канала
          </button>
        )}
        <button type="button" className="signature-save" disabled={busy} onClick={() => void run(() => onSave(draft))}>
          <Save size={14} />{busy ? "Сохраняю…" : "Сохранить подпись"}
        </button>
      </div>
      {linkOpen && (
        <div className="signature-link-backdrop" onMouseDown={() => setLinkOpen(false)}>
          <form className="signature-link-dialog" onMouseDown={(event) => event.stopPropagation()} onSubmit={submitLink}>
            <strong>Вставить ссылку</strong>
            <label>Текст ссылки<input autoFocus value={linkText} onChange={(event) => setLinkText(event.target.value)} /></label>
            <label>Адрес ссылки<input value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} placeholder="https://…" /></label>
            <div>
              <button type="button" onClick={() => setLinkOpen(false)}>Отмена</button>
              <button disabled={!linkText.trim() || !linkUrl.trim()}>Вставить</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

type ChannelSignatureSectionProps = {
  target: Target;
  onChanged?: () => Promise<void> | void;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

export function ChannelSignatureSection({ target, onChanged, onError, onNotice }: ChannelSignatureSectionProps) {
  const [current, setCurrent] = useState(target.default_signature ?? "");

  useEffect(() => {
    setCurrent(target.default_signature ?? "");
  }, [target.target_id, target.default_signature]);

  return (
    <section className="signature-block">
      <div className="signature-heading">
        <strong>Подпись канала</strong>
        <span>Автоматически подставляется к публикациям этого канала</span>
      </div>
      <MiniSignatureEditor
        value={current}
        onError={onError}
        onSave={async (value) => {
          const updated = await api.updateTarget(target.target_id, { default_signature: value.trim() || null });
          setCurrent(updated.default_signature ?? "");
          await onChanged?.();
          onNotice?.("Подпись канала сохранена");
        }}
      />
    </section>
  );
}

type PostSignatureSectionProps = {
  item: QueueItem;
  onUpdated?: (item: QueueItem) => void;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

export function PostSignatureSection({ item, onUpdated, onError, onNotice }: PostSignatureSectionProps) {
  const [targetSignature, setTargetSignature] = useState("");
  const [signature, setSignature] = useState(item.signature_text ?? "");
  const [isInherited, setInherited] = useState(item.signature_text == null);

  useEffect(() => {
    let cancelled = false;
    void api.target(item.target_id)
      .then((target) => {
        if (cancelled) return;
        const inherited = item.signature_text == null;
        const defaultSignature = target.default_signature ?? "";
        setTargetSignature(defaultSignature);
        setInherited(inherited);
        setSignature(inherited ? defaultSignature : item.signature_text ?? "");
      })
      .catch((exc) => {
        if (!cancelled) onError?.(exc instanceof Error ? exc.message : "Не удалось загрузить подпись канала");
      });
    return () => { cancelled = true; };
  }, [item.queue_item_id, item.target_id, item.signature_text]);

  return (
    <section className="signature-block post-signature-block">
      <div className="signature-heading">
        <strong>Подпись поста</strong>
        <span>Можно изменить только для этой публикации или оставить подпись канала</span>
      </div>
      <MiniSignatureEditor
        value={signature}
        inherited={isInherited}
        onError={onError}
        onSave={async (value) => {
          const updated = await api.updateQueueSignature(item.queue_item_id, value);
          setSignature(updated.signature_text ?? "");
          setInherited(false);
          onUpdated?.(updated);
          onNotice?.("Подпись поста сохранена");
        }}
        onReset={async () => {
          const updated = await api.updateQueueSignature(item.queue_item_id, null);
          setSignature(targetSignature);
          setInherited(true);
          onUpdated?.(updated);
          onNotice?.("Используется подпись канала");
        }}
      />
    </section>
  );
}
