import { ChangeEvent, useEffect, useState } from "react";
import { Play, Trash2, Upload } from "lucide-react";
import { api, QueueVideoInfo } from "../api";

type QueueVideoSectionProps = {
  queueItemId: number;
  readonly?: boolean;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

function humanSize(bytes: number) {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} МБ`
    : `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}

export function QueueVideoSection({
  queueItemId,
  readonly = false,
  onError,
  onNotice,
}: QueueVideoSectionProps) {
  const [info, setInfo] = useState<QueueVideoInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState("");

  async function load() {
    setLoadError("");
    try {
      setInfo(await api.queueVideoInfo(queueItemId));
    } catch (exc) {
      setLoadError(exc instanceof Error ? exc.message : "Не удалось загрузить сведения о видео");
    }
  }

  useEffect(() => {
    setInfo(null);
    void load();
  }, [queueItemId]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (!["video/mp4", "video/webm", "video/quicktime"].includes(file.type)) {
      onError("Поддерживаются MP4, WebM и MOV");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      onError("Видео больше 50 МБ");
      return;
    }

    setBusy(true);
    onError("");
    try {
      setInfo(await api.uploadQueueVideo(queueItemId, file));
      onNotice("Видео загружено. При публикации MAX подготовит файл и отправит пост автоматически, как только видео будет готово.");
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось загрузить видео");
    } finally {
      setBusy(false);
    }
  }

  async function remove(mediaId: string) {
    setBusy(true);
    onError("");
    try {
      setInfo(await api.deleteQueueVideo(queueItemId, mediaId));
      onNotice("Видео удалено");
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : "Не удалось удалить видео");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return <div className="video-enhancement-error">{loadError}</div>;
  }

  if (!info) return null;

  return (
    <div className="video-enhancement-block">
      {info.source_video_count > 0 && (
        <div className="video-source-warning">
          <div className="video-source-icon"><Play size={16} /></div>
          <div>
            <strong>В исходном посте есть видео{info.source_video_count > 1 ? ` (${info.source_video_count})` : ""}</strong>
            <p>Видео из VK пока не переносится автоматически. Если оно нужно в публикации, загрузите файл вручную ниже.</p>
          </div>
        </div>
      )}

      {info.uploaded_videos.length > 0 && (
        <>
          <div className="uploaded-video-list">
            {info.uploaded_videos.map((video) => (
              <div className="uploaded-video-card" key={video.media_id}>
                <video controls preload="metadata" src={video.source_url} />
                <div className="uploaded-video-meta">
                  <span>Видео добавлено вручную</span>
                  <small>{humanSize(video.size)}</small>
                  {!readonly && (
                    <button className="video-delete" type="button" disabled={busy} onClick={() => void remove(video.media_id)}>
                      <Trash2 size={14} />Удалить видео
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          {!readonly && (
            <div className="video-processing-note">
              <strong>Видео готово к публикации</strong>
              <span>После отправки MAX может несколько секунд обрабатывать файл. Пост опубликуется автоматически, как только видео будет готово.</span>
            </div>
          )}
        </>
      )}

      {!readonly && (
        <div className="video-upload-row">
          <label className="upload-media-button video-upload-button">
            <Upload size={17} />
            <span>{busy ? "Загрузка…" : "Добавить видео"}</span>
            <input
              type="file"
              accept="video/mp4,video/webm,video/quicktime"
              hidden
              disabled={busy}
              onChange={(event) => void upload(event)}
            />
          </label>
          <small className="video-upload-hint">MP4, WebM или MOV · до 50 МБ на файл.</small>
        </div>
      )}
    </div>
  );
}
