type QueueItemLite = {
  queue_item_id: number;
  target_name?: string | null;
  source_url?: string | null;
};

type UploadedVideo = {
  media_id: string;
  filename: string;
  source_url: string;
  size: number;
};

type SourceVideo = {
  attachment_id: number;
  external_attachment_id?: string | null;
  title: string;
  source_url?: string | null;
};

type VideoInfo = {
  source_video_count: number;
  source_videos: SourceVideo[];
  uploaded_videos: UploadedVideo[];
  source_video_import_supported: boolean;
};

const enhancedAttr = "data-video-enhanced-for";

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // оставляем HTTP-ошибку
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Не удалось прочитать видео"));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

function humanSize(bytes: number) {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} МБ`
    : `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}

async function resolveQueueItem(drawer: HTMLElement): Promise<QueueItemLite | null> {
  const sourceLink = drawer.querySelector<HTMLAnchorElement>(".drawer-source-row a")?.getAttribute("href") ?? "";
  const targetName = drawer.querySelector<HTMLElement>(".drawer-source-row strong")?.textContent?.trim() ?? "";
  if (!sourceLink || !targetName) return null;

  const items = await jsonRequest<QueueItemLite[]>("/api/v1/queue?limit=100");
  return items.find((item) => item.source_url === sourceLink && item.target_name === targetName) ?? null;
}

function renderSourceWarning(container: HTMLElement, info: VideoInfo) {
  if (!info.source_video_count) return;
  const warning = document.createElement("div");
  warning.className = "video-source-warning";
  warning.innerHTML = `
    <div class="video-source-icon">▶</div>
    <div>
      <strong>В исходном посте есть видео${info.source_video_count > 1 ? ` (${info.source_video_count})` : ""}</strong>
      <p>Само видео из VK пока не переносится автоматически. Если оно нужно в публикации, загрузите файл вручную ниже.</p>
    </div>
  `;
  container.append(warning);
}

function renderUploadedVideos(
  container: HTMLElement,
  queueItemId: number,
  info: VideoInfo,
  refresh: () => Promise<void>,
) {
  if (!info.uploaded_videos.length) return;

  const list = document.createElement("div");
  list.className = "uploaded-video-list";
  for (const video of info.uploaded_videos) {
    const card = document.createElement("div");
    card.className = "uploaded-video-card";

    const player = document.createElement("video");
    player.controls = true;
    player.preload = "metadata";
    player.src = video.source_url;

    const meta = document.createElement("div");
    meta.className = "uploaded-video-meta";
    meta.innerHTML = `<span>Видео добавлено вручную</span><small>${humanSize(video.size)}</small>`;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "video-delete";
    remove.textContent = "Удалить видео";
    remove.addEventListener("click", async () => {
      remove.disabled = true;
      try {
        await jsonRequest(`/api/v1/queue/${queueItemId}/video/${encodeURIComponent(video.media_id)}`, { method: "DELETE" });
        await refresh();
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Не удалось удалить видео");
        remove.disabled = false;
      }
    });

    meta.append(remove);
    card.append(player, meta);
    list.append(card);
  }
  container.append(list);
}

function renderUpload(
  container: HTMLElement,
  queueItemId: number,
  refresh: () => Promise<void>,
) {
  const row = document.createElement("div");
  row.className = "video-upload-row";

  const label = document.createElement("label");
  label.className = "upload-media-button video-upload-button";
  label.innerHTML = `
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
    <span>Добавить видео</span>
  `;

  const input = document.createElement("input");
  input.type = "file";
  input.accept = "video/mp4,video/webm,video/quicktime";
  input.hidden = true;
  label.append(input);

  const hint = document.createElement("small");
  hint.className = "video-upload-hint";
  hint.textContent = "MP4, WebM или MOV · до 50 МБ на файл.";

  const status = document.createElement("span");
  status.className = "video-upload-status";

  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    if (!["video/mp4", "video/webm", "video/quicktime"].includes(file.type)) {
      status.textContent = "Поддерживаются MP4, WebM и MOV";
      status.className = "video-upload-status error";
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      status.textContent = "Видео больше 50 МБ";
      status.className = "video-upload-status error";
      return;
    }

    input.disabled = true;
    status.textContent = "Загружаю видео…";
    status.className = "video-upload-status";
    try {
      await jsonRequest(`/api/v1/queue/${queueItemId}/video`, {
        method: "POST",
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type,
          data_base64: await fileToBase64(file),
        }),
      });
      status.textContent = "Видео загружено";
      status.className = "video-upload-status ok";
      await refresh();
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : "Не удалось загрузить видео";
      status.className = "video-upload-status error";
    } finally {
      input.disabled = false;
    }
  });

  row.append(label, hint, status);
  container.append(row);
}

async function enhanceDrawer(drawer: HTMLElement) {
  const item = await resolveQueueItem(drawer);
  if (!item) return;
  if (drawer.getAttribute(enhancedAttr) === String(item.queue_item_id)) return;
  drawer.setAttribute(enhancedAttr, String(item.queue_item_id));

  const media = drawer.querySelector<HTMLElement>(".drawer-media");
  if (!media) return;

  let block = media.querySelector<HTMLElement>(".video-enhancement-block");
  if (!block) {
    block = document.createElement("div");
    block.className = "video-enhancement-block";
    media.append(block);
  }

  const refresh = async () => {
    if (!block) return;
    block.innerHTML = "";
    try {
      const info = await jsonRequest<VideoInfo>(`/api/v1/queue/${item.queue_item_id}/video-info`);
      renderSourceWarning(block, info);
      renderUploadedVideos(block, item.queue_item_id, info, refresh);
      renderUpload(block, item.queue_item_id, refresh);
    } catch (error) {
      block.innerHTML = `<div class="video-enhancement-error">${error instanceof Error ? error.message : "Не удалось загрузить сведения о видео"}</div>`;
    }
  };

  await refresh();
}

function scan() {
  document.querySelectorAll<HTMLElement>(".editorial-drawer").forEach((drawer) => {
    void enhanceDrawer(drawer);
  });
}

const observer = new MutationObserver(scan);
observer.observe(document.documentElement, { childList: true, subtree: true });
scan();
