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
  original_text?: string | null;
  source_url?: string | null;
  source_published_at?: string | null;
  scheduled_at?: string | null;
  status: string;
  photos: QueuePhoto[];
};

export type Target = {
  target_id: number;
  name: string;
  platform: string;
  external_id: string;
  url?: string | null;
  is_active: boolean;
};

export type Source = {
  source_id: number;
  name: string;
  platform: string;
  url: string;
  is_active: boolean;
};

export type TargetSource = {
  target_source_id: number;
  target_id: number;
  source_id: number;
  is_active: boolean;
  rewrite_enabled: boolean;
};

export type CollectSummary = {
  status: string;
  sources_checked: number;
  posts_created: number;
  queue_items_created: number;
  errors: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
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
      // ignore malformed error body
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Не удалось прочитать файл"));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

export const api = {
  queue: () => request<QueueItem[]>("/api/v1/queue?limit=100"),
  queueItem: (id: number) => request<QueueItem>(`/api/v1/queue/${id}`),
  targets: () => request<Target[]>("/api/v1/targets?limit=100"),
  sources: () => request<Source[]>("/api/v1/sources?limit=100"),
  targetSources: (targetId: number) => request<TargetSource[]>(`/api/v1/targets/${targetId}/sources`),
  collectNow: () => request<CollectSummary>("/api/v1/system/collect-now", { method: "POST" }),

  createTarget: (data: Omit<Target, "target_id">) => request<Target>("/api/v1/targets", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  updateTarget: (id: number, data: Partial<Omit<Target, "target_id">>) => request<Target>(`/api/v1/targets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  }),
  deleteTarget: (id: number) => request<void>(`/api/v1/targets/${id}`, { method: "DELETE" }),

  createSource: (data: Omit<Source, "source_id">) => request<Source>("/api/v1/sources", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  updateSource: (id: number, data: Partial<Omit<Source, "source_id">>) => request<Source>(`/api/v1/sources/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  }),
  deleteSource: (id: number) => request<void>(`/api/v1/sources/${id}`, { method: "DELETE" }),

  attachSource: (targetId: number, sourceId: number) => request<TargetSource>(`/api/v1/targets/${targetId}/sources`, {
    method: "POST",
    body: JSON.stringify({ source_id: sourceId, is_active: true, rewrite_enabled: true }),
  }),
  updateTargetSource: (targetId: number, targetSourceId: number, data: Partial<Pick<TargetSource, "is_active" | "rewrite_enabled">>) =>
    request<TargetSource>(`/api/v1/targets/${targetId}/sources/${targetSourceId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  detachSource: (targetId: number, targetSourceId: number) => request<void>(`/api/v1/targets/${targetId}/sources/${targetSourceId}`, { method: "DELETE" }),

  updateQueueText: (id: number, rewritten_text: string) =>
    request<QueueItem>(`/api/v1/queue/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ rewritten_text }),
    }),
  submit: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/submit`, { method: "POST" }),
  approve: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/approve`, { method: "POST" }),
  reject: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reject`, { method: "POST" }),
  reopen: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reopen`, { method: "POST" }),
  schedule: (id: number, scheduledAt: string) => request<QueueItem>(`/api/v1/queue/${id}/schedule`, {
    method: "POST",
    body: JSON.stringify({ scheduled_at: scheduledAt }),
  }),
  deleteQueueItem: (id: number) => request<void>(`/api/v1/queue/${id}`, { method: "DELETE" }),
  uploadQueuePhoto: async (id: number, file: File) => request<QueueItem>(`/api/v1/queue/${id}/media`, {
    method: "POST",
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      data_base64: await fileToBase64(file),
    }),
  }),
  deleteQueuePhoto: (id: number, mediaId: string) => request<QueueItem>(`/api/v1/queue/${id}/media/${encodeURIComponent(mediaId)}`, {
    method: "DELETE",
  }),
};
