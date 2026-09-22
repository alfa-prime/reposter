const scheduleStepMs = 5 * 60 * 1000;
const scheduleSafetyMs = 60 * 1000;

export function localDateTimeValue(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hour = String(value.getHours()).padStart(2, "0");
  const minute = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

export function nextScheduleValue(now = new Date()): string {
  const nextSlot = Math.ceil(
    (now.getTime() + scheduleSafetyMs) / scheduleStepMs,
  ) * scheduleStepMs;
  return localDateTimeValue(new Date(nextSlot));
}

export function scheduleInputValue(
  scheduledAt?: string | null,
  now = new Date(),
): string {
  if (!scheduledAt) return nextScheduleValue(now);
  const parsed = new Date(scheduledAt);
  return Number.isNaN(parsed.getTime())
    ? nextScheduleValue(now)
    : localDateTimeValue(parsed);
}

export function scheduleValidationMessage(
  value: string,
  nowMs = Date.now(),
): string {
  if (!value) return "";
  const scheduledDate = new Date(value);
  if (Number.isNaN(scheduledDate.getTime())) {
    return "Укажите корректную дату и время публикации";
  }
  if (scheduledDate.getTime() <= nowMs) {
    return "Выбранное время уже прошло.";
  }
  return "";
}
