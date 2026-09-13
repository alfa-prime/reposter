export {};

type QueueItemLite = {
  status: string;
};

const ACTIVE_STATUSES = new Set([
  "pending",
  "rewriting",
  "awaiting_moderation",
  "approved",
  "scheduled",
]);

let refreshInFlight = false;

async function updateDashboardMetric() {
  const metrics = Array.from(document.querySelectorAll<HTMLElement>(".dashboard-grid .metric"));
  const metric = metrics.find((item) => item.querySelector("span")?.textContent?.trim() === "В очереди");
  if (!metric || refreshInFlight) return;

  refreshInFlight = true;
  try {
    const response = await fetch("/api/v1/queue?limit=100");
    if (!response.ok) return;
    const items = await response.json() as QueueItemLite[];
    const activeCount = items.filter((item) => ACTIVE_STATUSES.has(item.status)).length;

    const label = metric.querySelector<HTMLElement>("span");
    const value = metric.querySelector<HTMLElement>("strong");
    const note = metric.querySelector<HTMLElement>("small");

    if (label) label.textContent = "В работе";
    if (value) value.textContent = String(activeCount);
    if (note) note.textContent = `из ${items.length} материалов`;
  } catch {
    // Если API временно недоступен, оставляем исходный счетчик без вмешательства.
  } finally {
    refreshInFlight = false;
  }
}

function scan() {
  void updateDashboardMetric();
}

const observer = new MutationObserver(scan);
observer.observe(document.documentElement, { childList: true, subtree: true });
scan();
