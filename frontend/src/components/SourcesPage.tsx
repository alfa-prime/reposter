import { useState } from "react";
import { Database, Plus, Trash2 } from "lucide-react";
import { api, Source } from "../api";
import { CreateSourceModal } from "./CreateSourceModal";

type SourcesPageProps = {
  sources: Source[];
  busy: boolean;
  onChanged: () => Promise<void>;
  onDelete: (source: Source) => void;
  onError: (message: string) => void;
};

export function SourcesPage({
  sources,
  busy,
  onChanged,
  onDelete,
  onError,
}: SourcesPageProps) {
  const [createOpen, setCreateOpen] = useState(false);

  async function toggleSource(source: Source) {
    onError("");
    try {
      await api.updateSource(source.source_id, { is_active: !source.is_active });
      await onChanged();
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось изменить источник");
    }
  }

  return (
    <>
      <section className="table-card">
        <div className="table-head">
          <h2>Источники</h2>
          <div className="table-actions">
            <span>{sources.length} всего</span>
            <button
              className="primary compact"
              type="button"
              onClick={() => {
                onError("");
                setCreateOpen(true);
              }}
            >
              <Plus size={15} />Добавить
            </button>
          </div>
        </div>

        {sources.length === 0 && <div className="empty">Источников пока нет</div>}

        {sources.map((item) => (
          <div className="entity-row" key={item.source_id}>
            <div className="entity-icon"><Database size={18} /></div>
            <div className="entity-main">
              <strong>{item.name}</strong>
              <span>{item.platform} · {item.url}</span>
            </div>
            <button
              className={item.is_active ? "switch-label on clickable" : "switch-label clickable"}
              type="button"
              disabled={busy}
              onClick={() => void toggleSource(item)}
            >
              {item.is_active ? "Активен" : "Выключен"}
            </button>
            <button
              className="icon-button danger-icon"
              type="button"
              title="Удалить"
              onClick={() => onDelete(item)}
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </section>

      {createOpen && (
        <CreateSourceModal
          busy={busy}
          onClose={() => setCreateOpen(false)}
          onError={onError}
          onCreated={async () => {
            await onChanged();
          }}
        />
      )}
    </>
  );
}
