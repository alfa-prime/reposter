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
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const platform = detectSourcePlatform(url);
    if (platform !== "vk") {
      setUrlError("Укажите ссылку на источник VK, например: https://vk.com/имя_канала");
      return;
    }

    setUrlError("");
    onError("");
    try {
      await api.createSource({
        name: name.trim(),
        platform: "vk",
        url: url.trim(),
        is_active: true,
      });
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

        <p className="form-note"><span>*</span> обязательные поля</p>

        <form noValidate onSubmit={(event) => void submit(event)} className="form-grid">
          <label>
            Название <b>*</b>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              minLength={1}
              placeholder="Полуостров 51"
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
              type="text"
              inputMode="url"
              required
              placeholder="https://vk.com/peninsula51"
              aria-invalid={Boolean(urlError)}
            />
            {urlError && <small className="source-link-error">{urlError}</small>}
          </label>

          <button className="primary" disabled={busy}>Добавить источник</button>
        </form>
      </div>
    </div>
  );
}
