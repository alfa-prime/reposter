import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Bold,
  Italic,
  Link as LinkIcon,
  Pencil,
  Smile,
  Sparkles,
  Strikethrough,
  Underline,
  X,
} from "lucide-react";

const emojis = ["😀", "🙂", "😉", "😍", "🔥", "✨", "👍", "👏", "❤️", "📌", "📣", "⚡", "❗", "✅", "➡️", "🎉", "📷", "🚀"];

function normalizeUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

type QueueTextEditorProps = {
  value: string;
  originalText?: string | null;
  readonly?: boolean;
  editing: boolean;
  busy?: boolean;
  rewriteBusy?: boolean;
  canRewrite?: boolean;
  onEditingChange: (editing: boolean) => void;
  onChange: (value: string) => void;
  onRewrite?: () => void;
};

type LinkSelection = {
  start: number;
  end: number;
};

export function QueueTextEditor({
  value,
  originalText,
  readonly = false,
  editing,
  busy = false,
  rewriteBusy = false,
  canRewrite = false,
  onEditingChange,
  onChange,
  onRewrite,
}: QueueTextEditorProps) {
  const [showSource, setShowSource] = useState(false);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [linkText, setLinkText] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkError, setLinkError] = useState("");
  const [linkSelection, setLinkSelection] = useState<LinkSelection>({ start: 0, end: 0 });
  const textRef = useRef<HTMLTextAreaElement | null>(null);
  const linkTextRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!linkDialogOpen) return;
    requestAnimationFrame(() => linkTextRef.current?.focus());
  }, [linkDialogOpen]);

  function replaceSelection(prefix: string, suffix = prefix, placeholder = "текст") {
    const textarea = textRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.slice(start, end) || placeholder;
    const next = `${value.slice(0, start)}${prefix}${selectedText}${suffix}${value.slice(end)}`;
    onChange(next);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selectedText.length);
    });
  }

  function insertAtCursor(inserted: string) {
    const textarea = textRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    onChange(`${value.slice(0, start)}${inserted}${value.slice(end)}`);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + inserted.length, start + inserted.length);
    });
  }

  function openLinkDialog() {
    const textarea = textRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    setLinkSelection({ start, end });
    setLinkText(value.slice(start, end));
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

    const token = `[${label}](${url})`;
    const { start, end } = linkSelection;
    onChange(`${value.slice(0, start)}${token}${value.slice(end)}`);
    setLinkDialogOpen(false);
    setLinkError("");
    requestAnimationFrame(() => {
      const textarea = textRef.current;
      textarea?.focus();
      textarea?.setSelectionRange(start + token.length, start + token.length);
    });
  }

  return (
    <>
      <div className="drawer-text-section">
        <div className="drawer-section-title"><span>Текст поста</span><span>{value.length} знаков</span></div>

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
                <button type="button" title="Эмодзи" onClick={() => setEmojiOpen((current) => !current)}><Smile size={18}/></button>
                {emojiOpen && (
                  <div className="emoji-picker">
                    {emojis.map((emoji) => (
                      <button type="button" key={emoji} onClick={() => { insertAtCursor(emoji); setEmojiOpen(false); }}>{emoji}</button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <textarea ref={textRef} value={value} onChange={(event) => onChange(event.target.value)} rows={12} autoFocus/>
            <small className="format-hint">Поддерживается редакторская разметка: жирный, курсив, зачёркивание, подчёркивание, ссылки и эмодзи.</small>
          </div>
        ) : <div className="publication-text">{value || "—"}</div>}

        <div className="drawer-inline-actions">
          {canRewrite && onRewrite && (
            <button className="ai-rewrite-action" onClick={onRewrite} disabled={busy}>
              <Sparkles size={16}/>
              {rewriteBusy ? "Переписываю…" : value ? "Переписать с ИИ ещё раз" : "Переписать с ИИ"}
            </button>
          )}
          {!readonly && <button onClick={() => onEditingChange(!editing)} disabled={busy}><Pencil size={16}/>{editing ? "Закончить редактирование" : "Редактировать"}</button>}
          <button onClick={() => setShowSource((current) => !current)}>{showSource ? "Скрыть исходник" : "Показать текст источника"}</button>
        </div>
        {showSource && <div className="source-text-preview">{originalText || "—"}</div>}
      </div>

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
    </>
  );
}
