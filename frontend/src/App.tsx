import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Trash2, X } from "lucide-react";
import { api, QueueItem, Source, Target, TargetSource } from "./api";
import { AboutPage } from "./components/AboutPage";
import { Dashboard } from "./components/Dashboard";
import { QueuePage } from "./components/QueuePage";
import { SettingsPage } from "./components/SettingsPage";
import { Sidebar } from "./components/Sidebar";
import { SourcesPage } from "./components/SourcesPage";
import { TargetsPage } from "./components/TargetsPage";
import type { Section } from "./navigation";

type ConfirmDialog = {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
} | null;

const activeQueueStatuses = new Set([
  "pending",
  "rewriting",
  "awaiting_moderation",
  "approved",
  "scheduled",
]);

export function App() {
  const [section, setSection] = useState<Section>("queue");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null);
  const [targetSources, setTargetSources] = useState<TargetSource[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog>(null);

  const activeTargets = useMemo(() => targets.filter((item) => item.is_active).length, [targets]);
  const activeSources = useMemo(() => sources.filter((item) => item.is_active).length, [sources]);
  const activeQueue = useMemo(() => queue.filter((item) => activeQueueStatuses.has(item.status)).length, [queue]);

  async function loadAll() {
    setBusy(true);
    setError("");
    try {
      const [queueData, targetData, sourceData] = await Promise.all([
        api.queue(),
        api.targets(),
        api.sources(),
      ]);
      setQueue(queueData);
      setTargets(targetData);
      setSources(sourceData);

      if (selectedTarget) {
        const updatedTarget = targetData.find((item) => item.target_id === selectedTarget.target_id) ?? null;
        setSelectedTarget(updatedTarget);
        if (updatedTarget) {
          setTargetSources(await api.targetSources(updatedTarget.target_id));
        } else {
          setTargetSources([]);
        }
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить данные");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadAll(); }, []);

  async function openTarget(item: Target) {
    setSelectedTarget(item);
    setBusy(true);
    setError("");
    try {
      setTargetSources(await api.targetSources(item.target_id));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось загрузить источники канала");
    } finally {
      setBusy(false);
    }
  }

  async function collectNow() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.collectNow();
      if (result.sources_checked === 0) {
        if (sources.length === 0) {
          setSection("sources");
          setError("Сбор не запущен: сначала добавьте хотя бы один источник VK.");
        } else if (targets.length === 0) {
          setSection("targets");
          setError("Сбор не запущен: сначала добавьте целевой канал.");
        } else {
          setSection("targets");
          const firstActiveTarget = targets.find((item) => item.is_active) ?? targets[0];
          if (firstActiveTarget) await openTarget(firstActiveTarget);
          setError("Сбор не запущен: источник ещё не подключён к активному каналу. Выберите канал и нажмите «Подключить источник».");
        }
      } else if (result.errors > 0) {
        setError(`Сбор завершён с ошибками: проверено ${result.sources_checked}, ошибок ${result.errors}.`);
      } else {
        setNotice(`Проверено источников: ${result.sources_checked}. Новых постов: ${result.posts_created}. В очередь добавлено: ${result.queue_items_created}.`);
      }
      await loadAll();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Сбор не выполнен");
    } finally {
      setBusy(false);
    }
  }

  function askDeleteTarget(target: Target) {
    setConfirmDialog({
      title: "Удалить канал?",
      message: `Канал «${target.name}» будет удалён вместе с его связями и очередью публикаций.`,
      confirmLabel: "Удалить канал",
      onConfirm: async () => {
        await api.deleteTarget(target.target_id);
        setSelectedTarget(null);
        setTargetSources([]);
        await loadAll();
        setNotice("Канал удалён");
      },
    });
  }

  function askDeleteSource(source: Source) {
    setConfirmDialog({
      title: "Удалить источник?",
      message: `Источник «${source.name}» будет удалён вместе с уже собранными из него постами и элементами очереди. Это действие нельзя отменить.`,
      confirmLabel: "Удалить источник",
      onConfirm: async () => {
        await api.deleteSource(source.source_id);
        await loadAll();
        setNotice("Источник удалён");
      },
    });
  }

  async function confirmAction() {
    if (!confirmDialog) return;
    const action = confirmDialog.onConfirm;
    setConfirmDialog(null);
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Операция не выполнена");
    } finally {
      setBusy(false);
    }
  }

  const pageTitle = section === "queue"
    ? "Редакционная очередь"
    : section === "targets"
      ? "Целевые каналы"
      : section === "sources"
        ? "Источники"
        : "Обзор";

  const standalonePage = section === "about" || section === "settings";

  return (
    <div className="shell">
      <Sidebar section={section} onSectionChange={setSection} />

      <main className="workspace">
        {!standalonePage && <>
          <header className="topbar">
            <div>
              <p className="eyebrow">ДЯДЯ ВЛАД · ЧИТАЕТ НОВОСТИ</p>
              <h1>{pageTitle}</h1>
            </div>
            <button className="primary" onClick={() => void collectNow()} disabled={busy}>
              <RefreshCw size={17} className={busy ? "spin" : ""} />Собрать сейчас
            </button>
          </header>

          {(error || notice) && (
            <div className={error ? "toast error" : "toast"}>
              {error || notice}
              <button onClick={() => { setError(""); setNotice(""); }}>×</button>
            </div>
          )}
        </>}

        {section === "about" && <AboutPage />}
        {section === "settings" && <SettingsPage />}

        {section === "dashboard" && (
          <Dashboard
            activeTargets={activeTargets}
            totalTargets={targets.length}
            activeSources={activeSources}
            totalSources={sources.length}
            activeQueue={activeQueue}
            totalQueue={queue.length}
          />
        )}

        {section === "queue" && <QueuePage />}

        {section === "targets" && (
          <TargetsPage
            targets={targets}
            sources={sources}
            selectedTarget={selectedTarget}
            targetSources={targetSources}
            busy={busy}
            onOpenTarget={openTarget}
            onChanged={loadAll}
            onTargetSourcesChanged={setTargetSources}
            onDelete={askDeleteTarget}
            onError={setError}
            onNotice={setNotice}
          />
        )}

        {section === "sources" && (
          <SourcesPage
            sources={sources}
            busy={busy}
            onChanged={loadAll}
            onDelete={askDeleteSource}
            onError={setError}
            onNotice={setNotice}
          />
        )}
      </main>

      {confirmDialog && (
        <div className="modal-backdrop" onMouseDown={() => setConfirmDialog(null)}>
          <div className="modal-card confirm-card" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div>
                <p className="eyebrow">ПОДТВЕРЖДЕНИЕ</p>
                <h2>{confirmDialog.title}</h2>
              </div>
              <button className="icon-button" onClick={() => setConfirmDialog(null)}><X size={18} /></button>
            </div>
            <p className="confirm-message">{confirmDialog.message}</p>
            <div className="actions confirm-actions">
              <button className="secondary" onClick={() => setConfirmDialog(null)}>Отмена</button>
              <button className="danger" disabled={busy} onClick={() => void confirmAction()}>
                <Trash2 size={15} />{confirmDialog.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
