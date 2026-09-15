import { ImageOff } from "lucide-react";
import type { QueueItem } from "../api";
import "./QueuePostCard.css";

type QueuePostCardProps = {
  item: QueueItem;
  statusLabel: string;
  dateLabel: string;
  detailText: string;
  onOpen: () => void;
};

export function QueuePostCard({ item, statusLabel, dateLabel, detailText, onOpen }: QueuePostCardProps) {
  const cover = item.photos[0];

  return (
    <button className="editorial-post-card" onClick={onOpen}>
      {cover ? (
        <img src={cover.source_url} alt="" />
      ) : (
        <div className="editorial-card-no-media" aria-hidden="true">
          <ImageOff size={28} strokeWidth={1.6} />
          <span>Без медиа</span>
        </div>
      )}
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
