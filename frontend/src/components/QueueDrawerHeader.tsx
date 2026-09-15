import { CalendarClock, ExternalLink, X } from "lucide-react";
import { QueueItem } from "../api";

type QueueDrawerHeaderProps = {
  item: QueueItem;
  statusLabel: string;
  scheduledLabel?: string;
  errorMessage?: string;
  onClose: () => void;
};

function drawerTitle(status: string) {
  if (status === "published") return "Опубликованный пост";
  if (status === "scheduled") return "Публикация в очереди";
  if (status === "failed") return "Не удалось опубликовать";
  return "Публикация на модерации";
}

export function QueueDrawerHeader({
  item,
  statusLabel,
  scheduledLabel,
  errorMessage,
  onClose,
}: QueueDrawerHeaderProps) {
  return (
    <>
      <header className="editorial-drawer-head">
        <button className="drawer-close" onClick={onClose}><X size={22}/></button>
        <div>
          <h2>{drawerTitle(item.status)}</h2>
          <div className={`editorial-status status-${item.status}`}>{statusLabel}</div>
        </div>
      </header>

      {item.status === "scheduled" && scheduledLabel && (
        <div className="scheduled-banner">
          <CalendarClock size={18}/> Запланировано на {scheduledLabel}
        </div>
      )}

      {item.status === "failed" && errorMessage && (
        <div className="editorial-message error">
          <span><strong>Публикация не отправлена.</strong> {errorMessage}</span>
        </div>
      )}

      <div className="drawer-source-row">
        <div>
          <strong>{item.target_name ?? `Канал #${item.target_id}`}</strong>
          <span>Источник публикации</span>
        </div>
        {item.source_url && (
          <a href={item.source_url} target="_blank" rel="noreferrer">
            Перейти к посту <ExternalLink size={14}/>
          </a>
        )}
      </div>
    </>
  );
}
