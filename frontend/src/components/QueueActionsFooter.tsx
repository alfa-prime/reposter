import {
  CheckCircle2,
  RefreshCw,
  RotateCcw,
  Send,
  Trash2,
  XCircle,
} from "lucide-react";
import { QueueItem } from "../api";

type QueueActionsFooterProps = {
  item: QueueItem;
  editing: boolean;
  busy: boolean;
  onSaveText: () => void;
  onSubmit: () => void;
  onApprove: () => void;
  onReject: () => void;
  onPublishNow: () => void;
  onReopen: () => void;
  onDelete: () => void;
};

export function QueueActionsFooter({
  item,
  editing,
  busy,
  onSaveText,
  onSubmit,
  onApprove,
  onReject,
  onPublishNow,
  onReopen,
  onDelete,
}: QueueActionsFooterProps) {
  if (item.status === "publication_unknown") return null;
  const canSubmit = ["pending", "rewriting", "rejected"].includes(item.status);
  const awaitingModeration = item.status === "awaiting_moderation";
  const canPublishNow = ["approved", "scheduled", "failed"].includes(item.status) && item.target_platform === "max";
  const canReopen = ["approved", "scheduled", "rejected"].includes(item.status);

  return (
    <footer className="drawer-footer">
      <div className="drawer-main-actions">
        {editing && (
          <button className="secondary" onClick={onSaveText} disabled={busy}>
            Сохранить текст
          </button>
        )}

        {canSubmit && (
          <button className="primary" onClick={onSubmit} disabled={busy}>
            <Send size={17}/>
            На модерацию
          </button>
        )}

        {awaitingModeration && (
          <>
            <button className="primary" onClick={onApprove} disabled={busy}>
              <CheckCircle2 size={17}/>
              Согласовать пост
            </button>
            <button className="danger" onClick={onReject} disabled={busy}>
              <XCircle size={17}/>
              Отклонить
            </button>
          </>
        )}

        {canPublishNow && (
          <button className="primary" onClick={onPublishNow} disabled={busy}>
            {item.status === "failed" ? <RefreshCw size={17}/> : <Send size={17}/>} 
            {item.status === "failed" ? "Повторить публикацию" : "Опубликовать сейчас"}
          </button>
        )}

        {canReopen && (
          <button className="secondary" onClick={onReopen} disabled={busy}>
            <RotateCcw size={17}/>
            Вернуть в работу
          </button>
        )}
      </div>

      <button className="drawer-delete" onClick={onDelete} disabled={busy}>
        <Trash2 size={16}/>
        Удалить
      </button>
    </footer>
  );
}
