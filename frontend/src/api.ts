export type QueuePhoto = {
  attachment_id: number;
  external_attachment_id?: string | null;
  source_url: string;
  position: number;
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

export type CollectSummary = {
  status: string;
  sources_checked: number;
  posts_created: number;
  queue_items_created: number;
  errors: number;
};

const API_KEY_STORAGE = "reposter-api-key";

export function getApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE) ?? "";
}

export function setApiKey(value: string): void {
  localStorage.setItem(API_KEY_STORAGE, value.trim());
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = getApiKey();
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
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

export const api = {
  queue: () => request<QueueItem[]>("/api/v1/queue?limit=100"),
  targets: () => request<Target[]>("/api/v1/targets?limit=100"),
  sources: () => request<Source[]>("/api/v1/sources?limit=100"),
  collectNow: () => request<CollectSummary>("/api/v1/system/collect-now", { method: "POST" }),
  updateQueueText: (id: number, rewritten_text: string) =>
    request<QueueItem>(`/api/v1/queue/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ rewritten_text }),
    }),
  submit: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/submit`, { method: "POST" }),
  approve: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/approve`, { method: "POST" }),
  reject: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reject`, { method: "POST" }),
  reopen: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reopen`, { method: "POST" }),
};
