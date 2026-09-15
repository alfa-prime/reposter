import { FormEvent, useState } from "react";
import { X } from "lucide-react";
import { api, detectTargetPlatform, Target } from "../api";

type CreateTargetModalProps = {
  busy: boolean;
  onClose: () => void;
  onCreated: (target: Target) => Promise<void>;
  onError: (message: string) => void;
};

export function CreateTargetModal({ busy, onClose, onCreated, onError }: CreateTargetModalProps) {
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState("");
  const platform = detectTargetPlatform(url);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    if (platform !== "max") {
      setUrlError("Укажите ссылку на канал MAX, например: https://max.ru/имя_канала");
      return;
    }

    setUrlError("");
    onError("");
    try {
      const created = await api.createTarget({ url: url.trim(), is_active: true });
      await onCreated(created);
      onClose();
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось добавить канал");
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">НАСТРОЙКА</p>
            <h2>Новый канал</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <form noValidate onSubmit={(event) => void submit(event)} className="form-grid">
          <label className="wide">
            Ссылка на канал MAX
            <input
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                setUrlError("");
              }}
              type="text"
              inputMode="url"
              required
              autoFocus
              placeholder="https://max.ru/channel_51_news"
              aria-invalid={Boolean(urlError)}
            />
            {urlError && <small className="target-link-error">{urlError}</small>}
          </label>

          <div className="target-connect-panel wide">
            <div className="target-connect-help">
              <ol>
                <li>Добавьте бота <code>Neuro_writer_51</code> в подписчики канала.</li>
                <li>Назначьте бота администратором канала.</li>
                <li>Вставьте ссылку выше и нажмите «Добавить канал».</li>
              </ol>
              <p><b>Если бот был добавлен раньше:</b> один раз удалите его из канала и добавьте снова.</p>
            </div>
          </div>

          <button className="primary" disabled={busy || platform !== "max"}>
            {busy ? "Добавляю…" : "Добавить канал"}
          </button>
        </form>
      </div>
    </div>
  );
}
