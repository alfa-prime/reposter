export type QueuePhoto = {
  attachment_id: number;
  external_attachment_id?: string | null;
  source_url: string;
  position: number;
  kind?: "source" | "uploaded" | string;
  media_id?: string | null;
};

export type QueueItem = {
  queue_item_id: number;
  post_id: number;
  target_id: number;
  target_name?: string | null;
  target_platform?: string | null;
  target_url?: string | null;
  rewritten_text?: string | null;
  signature_text?: string | null;
  original_text?: string | null;
  source_url?: string | null;
  source_published_at?: string | null;
  scheduled_at?: string | null;
  error_message?: string | null;
  status: string;
  photos: QueuePhoto[];
};

export type QueueMediaState = { media_order: string[] };
export type UploadedVideo = { media_id: string; filename: string; source_url: string; size: number };
export type SourceVideo = { attachment_id: number; external_attachment_id?: string | null; title: string; source_url?: string | null };
export type QueueVideoInfo = { source_video_count: number; source_videos: SourceVideo[]; uploaded_videos: UploadedVideo[]; source_video_import_supported: boolean };

export type Target = {
  target_id: number;
  name: string;
  platform: string;
  external_id: string;
  url?: string | null;
  icon_url?: string | null;
  default_signature?: string | null;
  rewrite_prompt?: string | null;
  is_active: boolean;
};

export type Source = {
  source_id: number;
  name: string;
  platform: string;
  url: string;
  icon_url?: string | null;
  is_active: boolean;
};

export type TargetSource = { target_source_id: number; target_id: number; source_id: number; is_active: boolean; rewrite_enabled: boolean };
export type CollectSummary = { status: string; sources_checked: number; posts_created: number; queue_items_created: number; errors: number };
export type MaxChannelInfo = { chat_id: number; title?: string | null; link?: string | null; icon_url?: string | null; is_active?: boolean; last_event_type?: string | null; last_event_at?: string | null };
export type VKSourceInfo = { name: string; url: string; icon_url?: string | null };

export type TargetPlatform = "max" | "telegram" | "vk";
export type SourcePlatform = TargetPlatform;

function detectPlatform(value: string, requirePath = false): TargetPlatform | null {
  const raw = value.trim();
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    const host = url.hostname.toLowerCase().replace(/^www\./, "");
    const path = decodeURIComponent(url.pathname).replace(/^\/+|\/+$/g, "");
    if (requirePath && !path) return null;
    if (host === "max.ru") return "max";
    if (host === "t.me" || host === "telegram.me") return "telegram";
    if (host === "vk.com" || host === "vk.ru") return "vk";
  } catch { return null; }
  return null;
}

export function detectTargetPlatform(value: string): TargetPlatform | null { return detectPlatform(value); }
export function detectSourcePlatform(value: string): SourcePlatform | null { return detectPlatform(value, true); }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, cache: init?.cache ?? "no-store", headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        const messages = body.detail
          .map((item: unknown) => {
            if (typeof item !== "object" || item === null || !("msg" in item)) return "";
            return String(item.msg);
          })
          .filter(Boolean);
        if (messages.length) detail = messages.join("; ");
      }
    } catch { /* ignore malformed error body */ }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Не удалось прочитать файл"));
    reader.onload = () => { const result = String(reader.result ?? ""); resolve(result.includes(",") ? result.split(",", 2)[1] : result); };
    reader.readAsDataURL(file);
  });
}

async function createTargetFromLink(data: { url: string; is_active?: boolean }): Promise<Target> {
  const url = data.url.trim();
  if (!url) throw new Error("Укажите ссылку на канал");
  if (detectTargetPlatform(url) !== "max") throw new Error("Укажите ссылку на канал MAX, например https://max.ru/channel_name");
  const channel = await request<MaxChannelInfo>(`/api/v1/targets/resolve-max?link=${encodeURIComponent(url)}`);
  const name = channel.title?.trim();
  if (!name) throw new Error("MAX не вернул название канала");
  return request<Target>("/api/v1/targets", { method: "POST", body: JSON.stringify({ name, platform: "max", external_id: String(channel.chat_id), url: channel.link || url, icon_url: channel.icon_url || null, is_active: data.is_active ?? true }) });
}

async function createSourceFromLink(data: { url: string; is_active?: boolean }): Promise<Source> {
  const url = data.url.trim();
  if (!url) throw new Error("Укажите ссылку на источник");
  if (detectSourcePlatform(url) !== "vk") throw new Error("Укажите ссылку на источник VK, например https://vk.ru/peninsula51");
  const info = await request<VKSourceInfo>(`/api/v1/vk/source-info?link=${encodeURIComponent(url)}`);
  return request<Source>("/api/v1/sources", { method: "POST", body: JSON.stringify({ name: info.name, platform: "vk", url: info.url || url, icon_url: info.icon_url || null, is_active: data.is_active ?? true }) });
}

async function fetchAllQueueItems(): Promise<QueueItem[]> {
  const pageSize = 100;
  const items: QueueItem[] = [];
  let offset = 0;

  while (true) {
    const page = await request<QueueItem[]>(`/api/v1/queue?offset=${offset}&limit=${pageSize}`);
    items.push(...page);
    if (page.length < pageSize) return items;
    offset += pageSize;
  }
}

export const api = {
  queue: fetchAllQueueItems,
  queueItem: (id: number) => request<QueueItem>(`/api/v1/queue/${id}`),
  queueMediaState: (id: number) => request<QueueMediaState>(`/api/v1/queue/${id}/media-state`),
  updateQueueMediaState: (id: number, mediaOrder: string[]) => request<QueueMediaState>(`/api/v1/queue/${id}/media-state`, { method: "PUT", body: JSON.stringify({ media_order: mediaOrder }) }),
  queueVideoInfo: (id: number) => request<QueueVideoInfo>(`/api/v1/queue/${id}/video-info`),
  uploadQueueVideo: async (id: number, file: File) => request<UploadedVideo>(`/api/v1/queue/${id}/video`, { method: "POST", body: JSON.stringify({ filename: file.name, content_type: file.type, data_base64: await fileToBase64(file) }) }),
  deleteQueueVideo: (id: number, mediaId: string) => request<void>(`/api/v1/queue/${id}/video/${encodeURIComponent(mediaId)}`, { method: "DELETE" }),
  targets: () => request<Target[]>("/api/v1/targets?limit=100"),
  target: (id: number) => request<Target>(`/api/v1/targets/${id}`),
  sources: () => request<Source[]>("/api/v1/sources?limit=100"),
  targetSources: (targetId: number) => request<TargetSource[]>(`/api/v1/targets/${targetId}/sources`),
  collectNow: () => request<CollectSummary>("/api/v1/system/collect-now", { method: "POST" }),
  maxChannelByLink: (link: string) => request<MaxChannelInfo>(`/api/v1/targets/resolve-max?link=${encodeURIComponent(link)}`),
  createTarget: (data: { url: string; is_active?: boolean }) => createTargetFromLink(data),
  updateTarget: (id: number, data: Partial<Omit<Target, "target_id">>) => request<Target>(`/api/v1/targets/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTarget: (id: number) => request<void>(`/api/v1/targets/${id}`, { method: "DELETE" }),
  createSource: (data: { url: string; is_active?: boolean }) => createSourceFromLink(data),
  updateSource: (id: number, data: Partial<Omit<Source, "source_id">>) => request<Source>(`/api/v1/sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteSource: (id: number) => request<void>(`/api/v1/sources/${id}`, { method: "DELETE" }),
  attachSource: (targetId: number, sourceId: number) => request<TargetSource>(`/api/v1/targets/${targetId}/sources`, { method: "POST", body: JSON.stringify({ source_id: sourceId, is_active: true, rewrite_enabled: true }) }),
  updateTargetSource: (targetId: number, targetSourceId: number, data: Partial<Pick<TargetSource, "is_active" | "rewrite_enabled">>) => request<TargetSource>(`/api/v1/targets/${targetId}/sources/${targetSourceId}`, { method: "PATCH", body: JSON.stringify(data) }),
  detachSource: (targetId: number, targetSourceId: number) => request<void>(`/api/v1/targets/${targetId}/sources/${targetSourceId}`, { method: "DELETE" }),
  rewriteQueueItem: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/rewrite`, { method: "POST" }),
  updateQueueText: (id: number, rewritten_text: string) => request<QueueItem>(`/api/v1/queue/${id}`, { method: "PATCH", body: JSON.stringify({ rewritten_text }) }),
  updateQueueSignature: (id: number, signature_text: string | null) => request<QueueItem>(`/api/v1/queue/${id}`, { method: "PATCH", body: JSON.stringify({ signature_text }) }),
  submit: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/submit`, { method: "POST" }),
  approve: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/approve`, { method: "POST" }),
  reject: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reject`, { method: "POST" }),
  reopen: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reopen`, { method: "POST" }),
  schedule: (id: number, scheduledAt: string) => request<QueueItem>(`/api/v1/queue/${id}/schedule`, { method: "POST", body: JSON.stringify({ scheduled_at: scheduledAt }) }),
  publishNow: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/publish-now`, { method: "POST" }),
  deleteQueueItem: (id: number) => request<void>(`/api/v1/queue/${id}`, { method: "DELETE" }),
  uploadQueuePhoto: async (id: number, file: File) => request<QueueItem>(`/api/v1/queue/${id}/media`, { method: "POST", body: JSON.stringify({ filename: file.name, content_type: file.type, data_base64: await fileToBase64(file) }) }),
  deleteQueuePhoto: (id: number, mediaId: string) => request<QueueItem>(`/api/v1/queue/${id}/media/${encodeURIComponent(mediaId)}`, { method: "DELETE" }),
};
