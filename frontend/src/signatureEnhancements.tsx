import React, { FormEvent, useEffect, useRef, useState } from "react";
import { createRoot, Root } from "react-dom/client";
import { Bold, Italic, Link as LinkIcon, Save, Smile, Underline } from "lucide-react";
import { api, QueueItem, Target } from "./api";
import "./signatureEnhancements.css";

const emojis = ["📣", "👉", "✅", "❤️", "🔥", "✨", "📌", "➡️", "🙂", "👍"];

function normalizeUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

function MiniSignatureEditor({ value, onSave, inherited, onReset }: {
  value: string;
  onSave: (value: string) => Promise<void>;
  inherited?: boolean;
  onReset?: () => Promise<void>;
}) {
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
    setDraft(`${draft.slice(0, start)}${value}${draft.slice(end)}`);
    requestAnimationFrame(() => area.focus());
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

  async function save() {
    setBusy(true);
    try { await onSave(draft); } finally { setBusy(false); }
  }

  return <div className="signature-editor">
    {inherited && <div className="signature-inherited">Сейчас используется подпись канала по умолчанию</div>}
    <div className="signature-toolbar">
      <button type="button" title="Жирный" onClick={() => wrap("**")}><Bold size={15}/></button>
      <button type="button" title="Курсив" onClick={() => wrap("_")}><Italic size={15}/></button>
      <button type="button" title="Подчёркнутый" onClick={() => wrap("<u>", "</u>")}><Underline size={15}/></button>
      <button type="button" title="Ссылка" onClick={openLink}><LinkIcon size={15}/></button>
      <div className="signature-emoji-wrap">
        <button type="button" title="Эмодзи" onClick={() => setEmojiOpen(!emojiOpen)}><Smile size={16}/></button>
        {emojiOpen && <div className="signature-emoji">{emojis.map((emoji) => <button type="button" key={emoji} onClick={() => { insert(emoji); setEmojiOpen(false); }}>{emoji}</button>)}</div>}
      </div>
    </div>
    <textarea ref={ref} value={draft} onChange={(event) => setDraft(event.target.value)} rows={4} placeholder="Например: 📣 Подписывайтесь на наш канал"/>
    <div className="signature-actions">
      {onReset && !inherited && <button type="button" className="signature-secondary" onClick={() => void onReset()}>Вернуть подпись канала</button>}
      <button type="button" className="signature-save" disabled={busy} onClick={() => void save()}><Save size={14}/>{busy ? "Сохраняю…" : "Сохранить подпись"}</button>
    </div>
    {linkOpen && <div className="signature-link-backdrop" onMouseDown={() => setLinkOpen(false)}>
      <form className="signature-link-dialog" onMouseDown={(e) => e.stopPropagation()} onSubmit={submitLink}>
        <strong>Вставить ссылку</strong>
        <label>Текст ссылки<input autoFocus value={linkText} onChange={(e) => setLinkText(e.target.value)}/></label>
        <label>Адрес ссылки<input value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="https://…"/></label>
        <div><button type="button" onClick={() => setLinkOpen(false)}>Отмена</button><button disabled={!linkText.trim() || !linkUrl.trim()}>Вставить</button></div>
      </form>
    </div>}
  </div>;
}

function ChannelSignature({ target }: { target: Target }) {
  const [current, setCurrent] = useState(target.default_signature ?? "");
  return <section className="signature-block">
    <div className="signature-heading"><strong>Подпись канала</strong><span>Автоматически подставляется к публикациям этого канала</span></div>
    <MiniSignatureEditor value={current} onSave={async (value) => {
      const updated = await api.updateTarget(target.target_id, { default_signature: value.trim() || null });
      setCurrent(updated.default_signature ?? "");
    }}/>
  </section>;
}

function PostSignature({ item, target }: { item: QueueItem; target: Target }) {
  const inherited = item.signature_text == null;
  const [signature, setSignature] = useState(item.signature_text ?? target.default_signature ?? "");
  const [isInherited, setInherited] = useState(inherited);
  return <section className="signature-block post-signature-block">
    <div className="signature-heading"><strong>Подпись поста</strong><span>Можно изменить только для этой публикации или оставить подпись канала</span></div>
    <MiniSignatureEditor value={signature} inherited={isInherited} onSave={async (value) => {
      const updated = await api.updateQueueSignature(item.queue_item_id, value);
      setSignature(updated.signature_text ?? "");
      setInherited(false);
    }} onReset={async () => {
      await api.updateQueueSignature(item.queue_item_id, null);
      setSignature(target.default_signature ?? "");
      setInherited(true);
    }}/>
  </section>;
}

let channelRoot: Root | null = null;
let channelHost: HTMLElement | null = null;
let postRoot: Root | null = null;
let postHost: HTMLElement | null = null;
let scanning = false;

async function mountEnhancements() {
  const channelPanel = document.querySelector<HTMLElement>(".channel-panel");
  const channelTitle = channelPanel?.querySelector(".editor-head h2")?.textContent?.trim();
  if (channelPanel && channelTitle) {
    if (!channelHost || !channelHost.isConnected || channelHost.dataset.targetName !== channelTitle) {
      channelRoot?.unmount(); channelHost?.remove();
      const targets = await api.targets();
      const target = targets.find((item) => item.name === channelTitle);
      if (target) {
        channelHost = document.createElement("div");
        channelHost.className = "signature-enhancement-host";
        channelHost.dataset.targetName = channelTitle;
        const divider = channelPanel.querySelector(".section-divider");
        channelPanel.insertBefore(channelHost, divider ?? null);
        channelRoot = createRoot(channelHost);
        channelRoot.render(<ChannelSignature target={target}/>);
      }
    }
  } else if (channelHost) {
    channelRoot?.unmount(); channelHost.remove(); channelHost = null; channelRoot = null;
  }

  const drawer = document.querySelector<HTMLElement>(".editorial-drawer");
  const sourceLink = drawer?.querySelector<HTMLAnchorElement>(".drawer-source-row a")?.href;
  if (drawer && sourceLink) {
    if (!postHost || !postHost.isConnected || postHost.dataset.sourceUrl !== sourceLink) {
      postRoot?.unmount(); postHost?.remove();
      const items = await api.queue();
      const item = items.find((candidate) => candidate.source_url && new URL(candidate.source_url, location.origin).href === sourceLink);
      if (item) {
        const target = await api.target(item.target_id);
        postHost = document.createElement("div");
        postHost.className = "signature-enhancement-host";
        postHost.dataset.sourceUrl = sourceLink;
        const textSection = drawer.querySelector(".drawer-text-section");
        textSection?.insertAdjacentElement("afterend", postHost);
        postRoot = createRoot(postHost);
        postRoot.render(<PostSignature item={item} target={target}/>);
      }
    }
  } else if (postHost) {
    postRoot?.unmount(); postHost.remove(); postHost = null; postRoot = null;
  }
}

function scheduleMount() {
  if (scanning) return;
  scanning = true;
  requestAnimationFrame(() => {
    scanning = false;
    void mountEnhancements();
  });
}

new MutationObserver(scheduleMount).observe(document.body, { childList: true, subtree: true });
scheduleMount();
