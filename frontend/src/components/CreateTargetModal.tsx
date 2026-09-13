import { FormEvent, useMemo, useState } from "react";
import { X } from "lucide-react";
import { api, detectTargetPlatform, Target } from "../api";

type CreateTargetModalProps = {
  busy: boolean;
  onClose: () => void;
  onCreated: (target: Target) => Promise<void>;
  onError: (message: string) => void;
};

export function CreateTargetModal({ busy, onClose, onCreated, onError }: CreateTargetModalProps) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState("");
  const platform = useMemo(() => detectTargetPlatform(url), [url]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    if (!platform) {
      setUrlError("Укажите ссылку на канал MAX, Telegram или VK.");
      return;
    }

    setUrlError("");
    onError("");
    try {
      const created = await api.createTarget({
        name: name.trim(),
        url: url.trim(),
        is_active: true,
      });
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

        <p className="form-note"><span>*</span> обязательные поля</p>

        <form noValidate onSubmit={(event) => void submit(event)} className="form-grid">
          <label>
            Название <b>*</b>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              minLength={1}
              placeholder="Новости 51 региона"
            />
          </label>

          <label className="wide">
            Ссылка <b>*</b>
            <input
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                setUrlError("");
              }}
              type="url"
              inputMode="url"
              required
              placeholder="https://max.ru/channel_51_news"
              aria-invalid={Boolean(urlError)}
            />
            {urlError && <small className="target-link-error">{urlError}</small>}
          </label>

          {platform === "max" && (
            <div className="target-connect-panel wide">
              <div className="target-connect-help">
                <strong>Подключение MAX</strong>
                <ol>
                  <li>Добавьте бота <code>Neuro_writer_51</code> в подписчики канала.</li>
                  <li>Затем назначьте этого бота администратором канала.</li>
                  <li>После этого нажмите «Проверить и добавить канал».</li>
                </ol>
                <p><b>Важно:</b> если бот уже находился в канале до подключения сервиса, один раз удалите его, затем добавьте снова в подписчики и назначьте администратором.</p>
              </div>
            </div>
          )}

          <button className="primary" disabled={busy}>
            {platform === "max" ? "Проверить и добавить канал" : "Добавить канал"}
          </button>
        </form>
      </div>
    </div>
  );
}
