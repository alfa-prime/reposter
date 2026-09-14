import { useEffect, useMemo, useState } from "react";
import { RotateCcw, Save, Sparkles } from "lucide-react";
import { api, Target } from "../api";
import "../channelRewrite.css";

type ChannelRewriteSectionProps = {
  target: Target;
  onChanged?: () => Promise<void> | void;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

export function ChannelRewriteSection({
  target,
  onChanged,
  onError,
  onNotice,
}: ChannelRewriteSectionProps) {
  const [savedPrompt, setSavedPrompt] = useState(target.rewrite_prompt ?? "");
  const [draft, setDraft] = useState(target.rewrite_prompt ?? "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const prompt = target.rewrite_prompt ?? "";
    setSavedPrompt(prompt);
    setDraft(prompt);
  }, [target.target_id, target.rewrite_prompt]);

  const changed = useMemo(() => draft.trim() !== savedPrompt.trim(), [draft, savedPrompt]);
  const hasCustomPrompt = Boolean(savedPrompt.trim());

  async function save() {
    setBusy(true);
    onError?.("");
    try {
      const updated = await api.updateTarget(target.target_id, {
        rewrite_prompt: draft.trim() || null,
      });
      const prompt = updated.rewrite_prompt ?? "";
      setSavedPrompt(prompt);
      setDraft(prompt);
      await onChanged?.();
      onNotice?.(prompt ? "Инструкция для ИИ сохранена" : "Канал использует общую инструкцию для ИИ");
    } catch (exc) {
      onError?.(exc instanceof Error ? exc.message : "Не удалось сохранить инструкцию для ИИ");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    onError?.("");
    try {
      const updated = await api.updateTarget(target.target_id, { rewrite_prompt: null });
      setSavedPrompt(updated.rewrite_prompt ?? "");
      setDraft("");
      await onChanged?.();
      onNotice?.("Канал использует общую инструкцию для ИИ");
    } catch (exc) {
      onError?.(exc instanceof Error ? exc.message : "Не удалось вернуть общую инструкцию");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="channel-rewrite-block">
      <div className="channel-rewrite-heading">
        <div className="channel-rewrite-title">
          <span className="channel-rewrite-icon"><Sparkles size={17} /></span>
          <div>
            <strong>Рерайт с ИИ</strong>
            <span>Инструкция определяет, как ИИ будет переписывать посты именно для этого канала.</span>
          </div>
        </div>
        <span className={hasCustomPrompt ? "channel-rewrite-mode custom" : "channel-rewrite-mode"}>
          {hasCustomPrompt ? "Своя инструкция" : "Общая инструкция"}
        </span>
      </div>

      {!hasCustomPrompt && (
        <div className="channel-rewrite-inherited">
          Сейчас используется общая инструкция приложения. Заполните поле ниже, только если этому каналу нужен свой стиль.
        </div>
      )}

      <label className="channel-rewrite-field">
        <span>Инструкция для ИИ</span>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={8}
          maxLength={12000}
          disabled={busy}
          placeholder="Например: перепиши новость кратко и нейтрально, сохрани факты, имена, даты и ссылки; не добавляй сведения, которых нет в исходнике…"
        />
        <small>{draft.length.toLocaleString("ru-RU")} / 12 000 знаков</small>
      </label>

      <div className="channel-rewrite-actions">
        {hasCustomPrompt && (
          <button type="button" className="secondary" disabled={busy} onClick={() => void reset()}>
            <RotateCcw size={15} />
            Использовать общую
          </button>
        )}
        <button type="button" className="primary compact" disabled={busy || !changed} onClick={() => void save()}>
          <Save size={15} />
          {busy ? "Сохраняю…" : "Сохранить инструкцию"}
        </button>
      </div>
    </section>
  );
}
