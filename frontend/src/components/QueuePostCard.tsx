import type { QueueItem } from "../api";

type QueuePostCardProps = {
  item: QueueItem;
  statusLabel: string;
  dateLabel: string;
  detailText: string;
  onOpen: () => void;
};

export function QueuePostCard({ item, statusLabel, dateLabel, detailText, onOpen }: QueuePostCardProps) {
  return (
    <button className="editorial-post-card" onClick={onOpen}>
      {item.photos[0] && <img src={item.photos[0].source_url} alt="" />}
      <div className="editorial-card-body">
        <div className="editorial-card-meta">
          <span>{item.target_name ?? `Канал #${item.target_id}`}</span>
          <time>{dateLabel}</time>
        </div>
        <strong>{(item.rewritten_text ?? item.original_text ?? "Пост без текста").slice(0, 120)}</strong>
        <p>{detailText}</p>
        <div className={`editorial-status status-${item.status}`}>{statusLabel}</div>
      </div>
    </button>
  );
}
