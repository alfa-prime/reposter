import { useState } from "react";
import { ChevronRight, Database, ExternalLink, Link2, Plus, Radio, Trash2, X } from "lucide-react";
import { api, Source, Target, TargetSource } from "../api";
import { ChannelRewriteSection } from "./ChannelRewriteSection";
import { CreateTargetModal } from "./CreateTargetModal";
import { ChannelSignatureSection } from "./SignatureSections";

type TargetsPageProps = {
  targets: Target[];
  sources: Source[];
  selectedTarget: Target | null;
  targetSources: TargetSource[];
  busy: boolean;
  onOpenTarget: (target: Target) => Promise<void>;
  onChanged: () => Promise<void>;
  onTargetSourcesChanged: (items: TargetSource[]) => void;
  onDelete: (target: Target) => void;
  onError: (message: string) => void;
};

export function TargetsPage({
  targets,
  sources,
  selectedTarget,
  targetSources,
  busy,
  onOpenTarget,
  onChanged,
  onTargetSourcesChanged,
  onDelete,
  onError,
}: TargetsPageProps) {
  const [createOpen, setCreateOpen] = useState(false);
  const attachedSourceIds = new Set(targetSources.map((item) => item.source_id));

  async function toggleTarget(target: Target) {
    onError("");
    try {
      await api.updateTarget(target.target_id, { is_active: !target.is_active });
      await onChanged();
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось изменить канал");
    }
  }

  async function attachSource(sourceId: number) {
    if (!selectedTarget) return;
    onError("");
    try {
      await api.attachSource(selectedTarget.target_id, sourceId);
      onTargetSourcesChanged(await api.targetSources(selectedTarget.target_id));
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось подключить источник");
    }
  }

  async function detachSource(targetSourceId: number) {
    if (!selectedTarget) return;
    onError("");
    try {
      await api.detachSource(selectedTarget.target_id, targetSourceId);
      onTargetSourcesChanged(await api.targetSources(selectedTarget.target_id));
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось отключить источник");
    }
  }

  return (
    <>
      <section className="split-admin">
        <div className="table-card">
          <div className="table-head">
            <h2>Каналы</h2>
            <div className="table-actions">
              <span>{targets.length} всего</span>
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

          {targets.length === 0 && <div className="empty">Каналов пока нет</div>}

          {targets.map((item) => (
            <button
              className={`entity-row entity-button ${selectedTarget?.target_id === item.target_id ? "selected" : ""}`}
              key={item.target_id}
              type="button"
              onClick={() => void onOpenTarget(item)}
            >
              <div className="entity-icon"><Radio size={18} /></div>
              <div className="entity-main">
                <strong>{item.name}</strong>
              </div>
              <span className={item.is_active ? "switch-label on" : "switch-label"}>
                {item.is_active ? "Активен" : "Выключен"}
              </span>
              <ChevronRight size={16} />
            </button>
          ))}
        </div>

        <div className="editor-panel channel-panel">
          {!selectedTarget ? (
            <div className="empty large">
              <Radio size={34} />
              <h3>Выберите канал</h3>
              <p>Здесь будут настройки канала и его источники.</p>
            </div>
          ) : (
            <>
              <div className="editor-head">
                <div>
                  <span className="badge">{selectedTarget.platform}</span>
                  <h2>{selectedTarget.name}</h2>
                </div>
                {selectedTarget.url && (
                  <a href={selectedTarget.url} target="_blank" rel="noreferrer">
                    Открыть <ExternalLink size={14} />
                  </a>
                )}
              </div>

              <div className="actions">
                <button
                  className="secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => void toggleTarget(selectedTarget)}
                >
                  {selectedTarget.is_active ? "Отключить" : "Включить"}
                </button>
                <button className="danger" type="button" onClick={() => onDelete(selectedTarget)}>
                  <Trash2 size={15} />Удалить
                </button>
              </div>

              <ChannelRewriteSection
                target={selectedTarget}
                onChanged={onChanged}
                onError={onError}
              />

              <ChannelSignatureSection
                target={selectedTarget}
                onChanged={onChanged}
                onError={onError}
              />

              <div className="section-divider" />
              <div className="table-head embedded">
                <h2>Источники канала</h2>
                <span>{targetSources.length}</span>
              </div>

              {targetSources.length === 0 && (
                <div className="setup-hint">
                  <strong>Подключите источник</strong>
                  <span>Без этой связи сборщик не знает, в какой канал положить найденный пост.</span>
                </div>
              )}

              {targetSources.map((link) => {
                const source = sources.find((item) => item.source_id === link.source_id);
                return (
                  <div className="entity-row" key={link.target_source_id}>
                    <div className="entity-icon"><Database size={17} /></div>
                    <div className="entity-main">
                      <strong>{source?.name ?? `Источник #${link.source_id}`}</strong>
                      <span>{source?.url}</span>
                    </div>
                    <button
                      className="icon-button"
                      type="button"
                      title="Отключить источник"
                      onClick={() => void detachSource(link.target_source_id)}
                    >
                      <X size={16} />
                    </button>
                  </div>
                );
              })}

              <div className="attach-list">
                <label>Подключить источник</label>
                {sources
                  .filter((item) => !attachedSourceIds.has(item.source_id))
                  .map((source) => (
                    <button
                      key={source.source_id}
                      className="attach-source"
                      type="button"
                      onClick={() => void attachSource(source.source_id)}
                    >
                      <Link2 size={15} />
                      <span>{source.name}</span>
                      <small>{source.platform}</small>
                    </button>
                  ))}
                {sources.length === 0 && <div className="empty">Сначала добавьте источник в разделе «Источники»</div>}
                {sources.length > 0 && sources.every((item) => attachedSourceIds.has(item.source_id)) && (
                  <div className="empty">Все источники уже подключены</div>
                )}
              </div>
            </>
          )}
        </div>
      </section>

      {createOpen && (
        <CreateTargetModal
          busy={busy}
          onClose={() => setCreateOpen(false)}
          onError={onError}
          onCreated={async (target) => {
            await onChanged();
            await onOpenTarget(target);
          }}
        />
      )}
    </>
  );
}
