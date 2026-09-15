import { FormEvent, useState } from "react";
import { X } from "lucide-react";
import { api, detectSourcePlatform } from "../api";

type CreateSourceModalProps = {
  busy: boolean;
  onClose: () => void;
  onCreated: () => Promise<void>;
  onError: (message: string) => void;
};

export function CreateSourceModal({ busy, onClose, onCreated, onError }: CreateSourceModalProps) {
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    if (detectSourcePlatform(url) !== "vk") {
      setUrlError("Укажите ссылку на источник VK, например: https://vk.ru/peninsula51");
      return;
    }

    setUrlError("");
    onError("");
    try {
      await api.createSource({ url: url.trim(), is_active: true });
      await onCreated();
      onClose();
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось добавить источник");
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">НАСТРОЙКА</p>
            <h2>Новый источник</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <form noValidate onSubmit={(event) => void submit(event)} className="form-grid">
          <label className="wide">
            Ссылка на источник VK
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
              placeholder="https://vk.ru/peninsula51"
              aria-invalid={Boolean(urlError)}
            />
            {urlError && <small className="source-link-error">{urlError}</small>}
          </label>

          <button className="primary" disabled={busy || detectSourcePlatform(url) !== "vk"}>
            {busy ? "Добавляю…" : "Добавить источник"}
          </button>
        </form>
      </div>
    </div>
  );
}
