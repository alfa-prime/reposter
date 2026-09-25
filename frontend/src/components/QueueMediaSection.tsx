import { ChangeEvent } from "react";
import { ArrowLeft, ArrowRight, Eye, EyeOff, FileImage, Trash2, Upload } from "lucide-react";
import { QueueItem, QueuePhoto } from "../api";
import { QueueVideoSection } from "./QueueVideoSection";

type QueueMediaSectionProps = {
  item: QueueItem;
  orderedPhotos: QueuePhoto[];
  mediaOrder: string[];
  busy: boolean;
  mediaKey: (photo: QueuePhoto) => string;
  onRemoveAll: () => void;
  onRestoreAll: () => void;
  onTogglePhoto: (photo: QueuePhoto) => void;
  onMovePhoto: (photo: QueuePhoto, direction: -1 | 1) => void;
  onRemoveUploadedPhoto: (photo: QueuePhoto) => void;
  onOpenPhoto: (photo: QueuePhoto) => void;
  onUploadPhotos: (event: ChangeEvent<HTMLInputElement>) => void;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

export function QueueMediaSection({
  item,
  orderedPhotos,
  mediaOrder,
  busy,
  mediaKey,
  onRemoveAll,
  onRestoreAll,
  onTogglePhoto,
  onMovePhoto,
  onRemoveUploadedPhoto,
  onOpenPhoto,
  onUploadPhotos,
  onError,
  onNotice,
}: QueueMediaSectionProps) {
  const readonly = ["published", "publication_unknown"].includes(item.status);

  return (
    <div className="drawer-media">
      <div className="drawer-section-title media-section-title">
        <span>Медиа публикации</span>
        <div className="media-summary-actions">
          <span>В публикации {mediaOrder.length} из {item.photos.length}</span>
          {item.photos.length > 0 && !readonly && (
            <div className="media-bulk-actions">
              <button type="button" onClick={onRemoveAll} disabled={busy || mediaOrder.length === 0}>Убрать все</button>
              <button type="button" onClick={onRestoreAll} disabled={busy || mediaOrder.length === item.photos.length}>Вернуть все</button>
            </div>
          )}
        </div>
      </div>

      {item.photos.length > 0 ? (
        <div className="drawer-photo-grid">
          {orderedPhotos.map((photo) => {
            const key = mediaKey(photo);
            const included = mediaOrder.includes(key);
            const orderIndex = mediaOrder.indexOf(key);
            return (
              <div className={`drawer-photo ${included ? "included" : "excluded"}`} key={key}>
                <img src={photo.source_url} alt="Фото публикации" onClick={() => onOpenPhoto(photo)} />
                {!included && <div className="media-excluded-label">Не попадёт в публикацию</div>}
                {!readonly && (
                  <div className="media-controls media-controls-readable">
                    <button className={included ? "media-remove" : "media-restore"} title={included ? "Убрать фото из публикации" : "Вернуть фото в публикацию"} onClick={() => onTogglePhoto(photo)}>
                      {included ? <EyeOff size={14} /> : <Eye size={14} />}<span>{included ? "Убрать" : "Вернуть"}</span>
                    </button>
                    {included && <button title="Сдвинуть левее" disabled={orderIndex <= 0} onClick={() => onMovePhoto(photo, -1)}><ArrowLeft size={14} /></button>}
                    {included && <button title="Сдвинуть правее" disabled={orderIndex < 0 || orderIndex >= mediaOrder.length - 1} onClick={() => onMovePhoto(photo, 1)}><ArrowRight size={14} /></button>}
                    {photo.kind === "uploaded" && photo.media_id && (
                      <button className="media-delete-file" title="Удалить загруженный файл" onClick={() => onRemoveUploadedPhoto(photo)}>
                        <Trash2 size={14} /><span>Удалить файл</span>
                      </button>
                    )}
                  </div>
                )}
                <span>{photo.kind === "uploaded" ? "Добавлено вручную" : included ? `№ ${orderIndex + 1}` : "Исключено"}</span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="no-media"><FileImage size={28} /><span>У публикации пока нет фотографий</span></div>
      )}

      {!readonly && (
        <>
          <label className="upload-media-button">
            <Upload size={17} />Добавить фото
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={onUploadPhotos} disabled={busy} />
          </label>
          <small>«Убрать» исключает исходное фото только из публикации — сам оригинал остаётся. Загруженные вручную файлы можно удалить полностью · JPEG, PNG или WebP · до 10 МБ на файл.</small>
        </>
      )}

      <QueueVideoSection
        queueItemId={item.queue_item_id}
        readonly={readonly}
        onError={onError}
        onNotice={onNotice}
      />
    </div>
  );
}
