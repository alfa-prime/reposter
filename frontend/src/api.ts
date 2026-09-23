export type QueuePhoto = {
  attachment_id: number;
  external_attachment_id?: string | null;
  source_url: string;
  position: number;
  kind?: "source" | "uploaded" | string;
  media_id?: string | null;
};

export type CurrentUserRole = {
  code: string;
  name: string;
};

export type CurrentUser = {
  user_id: number;
  username: string;
  display_name: string;
  avatar_url?: string | null;
  must_change_password: boolean;
  roles: CurrentUserRole[];
  permissions: string[];
};

export type LoginCredentials = {
  username: string;
  password: string;
};

export type PasswordChange = {
  current_password: string;
  new_password: string;
};

export type AdminRole = {
  code: string;
  name: string;
  description?: string | null;
  is_system: boolean;
  permissions: string[];
};

export type AdminUser = {
  user_id: number;
  username: string;
  display_name: string;
  avatar_url?: string | null;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
  roles: AdminRole[];
  target_ids: number[];
};

export type AdminUserCreate = {
  username: string;
  display_name: string;
  temporary_password: string;
  role_codes: string[];
  target_ids: number[];
};

export type AdminUserUpdate = {
  display_name?: string;
  is_active?: boolean;
  role_codes?: string[];
  target_ids?: number[];
};

export type AuditEvent = {
  audit_event_id: number;
  actor_user_id: number | null;
  actor_name: string | null;
  actor_username: string | null;
  action: string;
  subject_type: string;
  subject_id: number;
  subject_name: string | null;
  subject_username: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type AuditEventPage = {
  items: AuditEvent[];
  total: number;
  offset: number;
  limit: number;
};

export type EditorialAuditEvent = {
  audit_event_id: number; actor_user_id: number | null; actor_name: string | null; actor_username: string | null;
  action: string; queue_item_id: number; post_id: number | null; target_id: number | null; target_name: string | null;
  details: Record<string, unknown>; created_at: string;
};
export type EditorialAuditEventPage = { items: EditorialAuditEvent[]; total: number; offset: number; limit: number };

export const AUTH_SESSION_EXPIRED_EVENT = "reposter:auth-session-expired";

export class ApiError extends Error {
  readonly status: number;
  readonly retryAfter: number | null;

  constructor(message: string, status: number, retryAfter: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

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

export type QueuePage = {
  items: QueueItem[];
  total: number;
  offset: number;
  limit: number;
  status_counts: Record<string, number>;
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
export type CollectSummary = { status: string; run_id: number; sources_total: number; sources_checked: number; sources_succeeded: number; posts_found: number; posts_created: number; queue_items_created: number; errors: number };
export type MaxChannelInfo = { chat_id: number; title?: string | null; link?: string | null; icon_url?: string | null; is_active?: boolean; last_event_type?: string | null; last_event_at?: string | null };
export type VKSourceInfo = { name: string; url: string; icon_url?: string | null };

export type CollectionRunStatus = "running" | "success" | "partial" | "failed" | "skipped" | "interrupted";
export type CollectionRunTrigger = "manual" | "scheduled";
export type CollectionSettings = { enabled: boolean; interval_minutes: number; start_time: string; end_time: string; timezone: string; updated_at: string };
export type CollectionRun = { collection_run_id: number; trigger: CollectionRunTrigger; status: CollectionRunStatus; started_at: string; finished_at?: string | null; sources_total: number; sources_checked: number; sources_succeeded: number; sources_failed: number; posts_found: number; posts_created: number; queue_items_created: number; error_message?: string | null };
export type CollectionSourceRun = { collection_source_run_id: number; source_id?: number | null; source_name: string; source_url: string; status: "running" | "success" | "no_changes" | "failed" | "interrupted"; started_at: string; finished_at?: string | null; last_post_id_before?: string | null; last_post_id_after?: string | null; posts_found: number; posts_created: number; queue_items_created: number; error_type?: string | null; error_message?: string | null };
export type CollectionRunDetail = CollectionRun & { source_runs: CollectionSourceRun[] };
export type CollectionRunPage = { items: CollectionRun[]; total: number; offset: number; limit: number };
export type CollectionStatus = { enabled: boolean; running: boolean; next_run_at?: string | null; last_run?: CollectionRun | null; last_success_at?: string | null; consecutive_failures: number };

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

async function request<T>(
  path: string,
  init?: RequestInit,
  options: { notifyUnauthorized?: boolean } = {},
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    cache: init?.cache ?? "no-store",
    credentials: init?.credentials ?? "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
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
    if (response.status === 401 && options.notifyUnauthorized !== false) {
      window.dispatchEvent(new Event(AUTH_SESSION_EXPIRED_EVENT));
    }
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfter = retryAfterHeader === null ? null : Number.parseInt(retryAfterHeader, 10);
    throw new ApiError(
      detail,
      response.status,
      Number.isFinite(retryAfter) ? retryAfter : null,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function cookieValue(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  if (!item) return null;
  return decodeURIComponent(item.slice(prefix.length));
}

function csrfToken(): string {
  const token = cookieValue("__Host-rp_csrf") ?? cookieValue("rp_csrf");
  if (!token) throw new ApiError("CSRF-токен сессии отсутствует", 403);
  return token;
}

function csrfHeaders(): Record<string, string> {
  return { "X-CSRF-Token": csrfToken() };
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
  return request<Target>("/api/v1/targets", { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ name, platform: "max", external_id: String(channel.chat_id), url: channel.link || url, icon_url: channel.icon_url || null, is_active: data.is_active ?? true }) });
}

async function createSourceFromLink(data: { url: string; is_active?: boolean }): Promise<Source> {
  const url = data.url.trim();
  if (!url) throw new Error("Укажите ссылку на источник");
  if (detectSourcePlatform(url) !== "vk") throw new Error("Укажите ссылку на источник VK, например https://vk.ru/peninsula51");
  const info = await request<VKSourceInfo>(`/api/v1/vk/source-info?link=${encodeURIComponent(url)}`);
  return request<Source>("/api/v1/sources", { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ name: info.name, platform: "vk", url: info.url || url, icon_url: info.icon_url || null, is_active: data.is_active ?? true }) });
}

async function fetchQueuePage(options: {
  offset: number;
  limit: number;
  targetId: number | null;
  statuses: string[];
}): Promise<QueuePage> {
  const params = new URLSearchParams({
    offset: String(options.offset),
    limit: String(options.limit),
  });
  if (options.targetId !== null) params.set("target_id", String(options.targetId));
  options.statuses.forEach((status) => params.append("status", status));
  return request<QueuePage>(`/api/v1/queue/page?${params.toString()}`);
}

export const api = {
  login: (credentials: LoginCredentials) => request<CurrentUser>(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify(credentials) },
    { notifyUnauthorized: false },
  ),
  currentUser: () => request<CurrentUser>(
    "/api/v1/auth/me",
    undefined,
    { notifyUnauthorized: false },
  ),
  changePassword: (passwords: PasswordChange) => request<CurrentUser>(
    "/api/v1/auth/change-password",
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken() },
      body: JSON.stringify(passwords),
    },
  ),
  uploadAvatar: async (file: File) => request<CurrentUser>(
    "/api/v1/auth/avatar",
    {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type,
        data_base64: await fileToBase64(file),
      }),
    },
  ),
  deleteAvatar: () => request<CurrentUser>("/api/v1/auth/avatar", {
    method: "DELETE",
    headers: csrfHeaders(),
  }),
  logout: () => request<void>("/api/v1/auth/logout", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken() },
  }),
  logoutAll: () => request<void>("/api/v1/auth/logout-all", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken() },
  }),
  adminUsers: () => request<AdminUser[]>("/api/v1/admin/users"),
  adminRoles: () => request<AdminRole[]>("/api/v1/admin/roles"),
  auditEvents: (options: { offset: number; limit: number; actorUserId?: number; action?: string }) => {
    const params = new URLSearchParams({ offset: String(options.offset), limit: String(options.limit) });
    if (options.actorUserId) params.set("actor_user_id", String(options.actorUserId));
    if (options.action) params.set("action", options.action);
    return request<AuditEventPage>(`/api/v1/admin/audit?${params.toString()}`);
  },
  editorialAuditEvents: (options: { offset: number; limit: number; actorUserId?: number; targetId?: number; action?: string; dateFrom?: string; dateTo?: string }) => {
    const params = new URLSearchParams({ offset: String(options.offset), limit: String(options.limit) });
    if (options.actorUserId) params.set("actor_user_id", String(options.actorUserId));
    if (options.targetId) params.set("target_id", String(options.targetId));
    if (options.action) params.set("action", options.action);
    if (options.dateFrom) params.set("date_from", options.dateFrom);
    if (options.dateTo) params.set("date_to", options.dateTo);
    return request<EditorialAuditEventPage>(`/api/v1/admin/audit/editorial?${params.toString()}`);
  },
  createAdminUser: (data: AdminUserCreate) => request<AdminUser>(
    "/api/v1/admin/users",
    { method: "POST", headers: csrfHeaders(), body: JSON.stringify(data) },
  ),
  updateAdminUser: (id: number, data: AdminUserUpdate) => request<AdminUser>(
    `/api/v1/admin/users/${id}`,
    { method: "PATCH", headers: csrfHeaders(), body: JSON.stringify(data) },
  ),
  resetAdminUserPassword: (id: number, temporaryPassword: string) => request<AdminUser>(
    `/api/v1/admin/users/${id}/reset-password`,
    { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ temporary_password: temporaryPassword }) },
  ),
  revokeAdminUserSessions: (id: number) => request<{ revoked_sessions: number }>(
    `/api/v1/admin/users/${id}/revoke-sessions`,
    { method: "POST", headers: csrfHeaders() },
  ),
  queuePage: fetchQueuePage,
  queueItem: (id: number) => request<QueueItem>(`/api/v1/queue/${id}`),
  queueMediaState: (id: number) => request<QueueMediaState>(`/api/v1/queue/${id}/media-state`),
  updateQueueMediaState: (id: number, mediaOrder: string[]) => request<QueueMediaState>(`/api/v1/queue/${id}/media-state`, { method: "PUT", headers: csrfHeaders(), body: JSON.stringify({ media_order: mediaOrder }) }),
  queueVideoInfo: (id: number) => request<QueueVideoInfo>(`/api/v1/queue/${id}/video-info`),
  uploadQueueVideo: async (id: number, file: File) => request<UploadedVideo>(`/api/v1/queue/${id}/video`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ filename: file.name, content_type: file.type, data_base64: await fileToBase64(file) }) }),
  deleteQueueVideo: (id: number, mediaId: string) => request<void>(`/api/v1/queue/${id}/video/${encodeURIComponent(mediaId)}`, { method: "DELETE", headers: csrfHeaders() }),
  targets: () => request<Target[]>("/api/v1/targets?limit=100"),
  target: (id: number) => request<Target>(`/api/v1/targets/${id}`),
  sources: () => request<Source[]>("/api/v1/sources?limit=100"),
  targetSources: (targetId: number) => request<TargetSource[]>(`/api/v1/targets/${targetId}/sources`),
  collectNow: () => request<CollectSummary>("/api/v1/system/collect-now", { method: "POST", headers: csrfHeaders() }),
  collectionSettings: () => request<CollectionSettings>("/api/v1/system/collection/settings"),
  updateCollectionSettings: (data: Omit<CollectionSettings, "updated_at">) => request<CollectionSettings>("/api/v1/system/collection/settings", { method: "PUT", headers: csrfHeaders(), body: JSON.stringify(data) }),
  collectionStatus: () => request<CollectionStatus>("/api/v1/system/collection/status"),
  collectionRuns: (options: { offset: number; limit: number; status?: string; trigger?: string }) => {
    const params = new URLSearchParams({ offset: String(options.offset), limit: String(options.limit) });
    if (options.status) params.set("status", options.status);
    if (options.trigger) params.set("trigger", options.trigger);
    return request<CollectionRunPage>(`/api/v1/system/collection/runs?${params.toString()}`);
  },
  collectionRun: (id: number) => request<CollectionRunDetail>(`/api/v1/system/collection/runs/${id}`),
  maxChannelByLink: (link: string) => request<MaxChannelInfo>(`/api/v1/targets/resolve-max?link=${encodeURIComponent(link)}`),
  createTarget: (data: { url: string; is_active?: boolean }) => createTargetFromLink(data),
  updateTarget: (id: number, data: Partial<Omit<Target, "target_id">>) => request<Target>(`/api/v1/targets/${id}`, { method: "PATCH", headers: csrfHeaders(), body: JSON.stringify(data) }),
  deleteTarget: (id: number) => request<void>(`/api/v1/targets/${id}`, { method: "DELETE", headers: csrfHeaders() }),
  createSource: (data: { url: string; is_active?: boolean }) => createSourceFromLink(data),
  updateSource: (id: number, data: Partial<Omit<Source, "source_id">>) => request<Source>(`/api/v1/sources/${id}`, { method: "PATCH", headers: csrfHeaders(), body: JSON.stringify(data) }),
  deleteSource: (id: number) => request<void>(`/api/v1/sources/${id}`, { method: "DELETE", headers: csrfHeaders() }),
  attachSource: (targetId: number, sourceId: number) => request<TargetSource>(`/api/v1/targets/${targetId}/sources`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ source_id: sourceId, is_active: true, rewrite_enabled: true }) }),
  updateTargetSource: (targetId: number, targetSourceId: number, data: Partial<Pick<TargetSource, "is_active" | "rewrite_enabled">>) => request<TargetSource>(`/api/v1/targets/${targetId}/sources/${targetSourceId}`, { method: "PATCH", headers: csrfHeaders(), body: JSON.stringify(data) }),
  detachSource: (targetId: number, targetSourceId: number) => request<void>(`/api/v1/targets/${targetId}/sources/${targetSourceId}`, { method: "DELETE", headers: csrfHeaders() }),
  rewriteQueueItem: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/rewrite`, { method: "POST", headers: csrfHeaders() }),
  updateQueueText: (id: number, rewritten_text: string) => request<QueueItem>(`/api/v1/queue/${id}`, { method: "PATCH", headers: csrfHeaders(), body: JSON.stringify({ rewritten_text }) }),
  updateQueueSignature: (id: number, signature_text: string | null) => request<QueueItem>(`/api/v1/queue/${id}`, { method: "PATCH", headers: csrfHeaders(), body: JSON.stringify({ signature_text }) }),
  submit: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/submit`, { method: "POST", headers: csrfHeaders() }),
  approve: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/approve`, { method: "POST", headers: csrfHeaders() }),
  reject: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reject`, { method: "POST", headers: csrfHeaders() }),
  reopen: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/reopen`, { method: "POST", headers: csrfHeaders() }),
  schedule: (id: number, scheduledAt: string) => request<QueueItem>(`/api/v1/queue/${id}/schedule`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ scheduled_at: scheduledAt }) }),
  publishNow: (id: number) => request<QueueItem>(`/api/v1/queue/${id}/publish-now`, { method: "POST", headers: csrfHeaders() }),
  deleteQueueItem: (id: number) => request<void>(`/api/v1/queue/${id}`, { method: "DELETE", headers: csrfHeaders() }),
  uploadQueuePhoto: async (id: number, file: File) => request<QueueItem>(`/api/v1/queue/${id}/media`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ filename: file.name, content_type: file.type, data_base64: await fileToBase64(file) }) }),
  deleteQueuePhoto: (id: number, mediaId: string) => request<QueueItem>(`/api/v1/queue/${id}/media/${encodeURIComponent(mediaId)}`, { method: "DELETE", headers: csrfHeaders() }),
};
