import { ApiError, api, BackgroundTask, CollectSummary } from "./api";

const storageKey = "reposter:collection-task";
type StoredTask = { idempotencyKey: string; taskId?: string };

function savedTask(): StoredTask | null {
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) return null;
    const task = JSON.parse(raw) as StoredTask;
    return typeof task.idempotencyKey === "string" ? task : null;
  } catch { return null; }
}

function saveTask(task: StoredTask) {
  window.sessionStorage.setItem(storageKey, JSON.stringify(task));
}

/** Wait for a manual collection while allowing the user to continue using the app. */
export async function collectNowInBackground(signal?: AbortSignal): Promise<CollectSummary> {
  const stored = savedTask() ?? { idempotencyKey: crypto.randomUUID() };
  if (!stored.taskId) {
    saveTask(stored); // A lost POST response can be retried with the same key.
    try {
      const task = await api.submitCollectionTask(stored.idempotencyKey);
      stored.taskId = task.task_id;
      saveTask(stored);
    } catch (exc) {
      if (exc instanceof ApiError && exc.status === 503 && exc.message === "Фоновое исполнение ещё не включено") {
        window.sessionStorage.removeItem(storageKey);
        return api.collectNow();
      }
      if (exc instanceof ApiError && [400, 403, 404, 409, 422].includes(exc.status)) window.sessionStorage.removeItem(storageKey);
      throw exc;
    }
  }
  while (true) {
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    let task: BackgroundTask;
    try {
      task = await api.backgroundTask(stored.taskId, signal);
    } catch (exc) {
      if (exc instanceof ApiError && [403, 404].includes(exc.status)) window.sessionStorage.removeItem(storageKey);
      throw exc;
    }
    if (task.state === "succeeded") {
      window.sessionStorage.removeItem(storageKey);
      const summary = task.result as CollectSummary | null;
      if (!summary || typeof summary.sources_checked !== "number") throw new Error("Результат сбора недоступен. Проверьте журнал запусков.");
      return summary;
    }
    if (["failed", "cancelled", "needs_review"].includes(task.state)) {
      window.sessionStorage.removeItem(storageKey);
      throw new Error(task.error_code === "vk_not_configured" ? "Токен VK не настроен." : "Сбор не завершился. Проверьте журнал запусков.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, task.state === "retry_wait" ? 10_000 : 5000));
  }
}
