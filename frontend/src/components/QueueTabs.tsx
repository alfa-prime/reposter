import { AlertTriangle, Archive, ClipboardCheck, Clock3, Inbox, RefreshCw } from "lucide-react";

export type QueueTab = "storage" | "moderation" | "scheduled" | "attention" | "archive";

export const queueTabConfig: Record<QueueTab, { label: string; statuses: string[] }> = {
  storage: { label: "Хранилище постов", statuses: ["pending", "rewriting", "rejected"] },
  moderation: { label: "На модерации", statuses: ["awaiting_moderation"] },
  scheduled: { label: "Очередь публикаций", statuses: ["approved", "scheduled"] },
  attention: { label: "Требуют внимания", statuses: ["publication_unknown"] },
  archive: { label: "Архив", statuses: ["published", "failed"] },
};

type QueueTabsProps = {
  tab: QueueTab;
  counts: Record<QueueTab, number>;
  busy: boolean;
  onChange: (tab: QueueTab) => void;
  onRefresh: () => void;
};

export function QueueTabs({ tab, counts, busy, onChange, onRefresh }: QueueTabsProps) {
  return (
    <div className="editorial-tabs" role="tablist" aria-label="Разделы очереди">
      {(Object.keys(queueTabConfig) as QueueTab[]).map((key) => (
        <button
          key={key}
          className={tab === key ? "active" : ""}
          onClick={() => onChange(key)}
          role="tab"
        >
          {key === "storage"
            ? <Inbox size={17} />
            : key === "moderation"
              ? <ClipboardCheck size={17} />
              : key === "scheduled"
              ? <Clock3 size={17} />
              : key === "attention"
                ? <AlertTriangle size={17} />
                : <Archive size={17} />}
          <span>{queueTabConfig[key].label}</span>
          <b>{counts[key]}</b>
        </button>
      ))}
      <button className="editorial-refresh" onClick={onRefresh} disabled={busy} title="Обновить">
        <RefreshCw size={17} className={busy ? "spin" : ""} />
      </button>
    </div>
  );
}
