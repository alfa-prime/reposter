import assert from "node:assert/strict";
import test from "node:test";

process.env.TZ = "Europe/Moscow";

const {
  localDateTimeValue,
  nextScheduleValue,
  scheduleInputValue,
  scheduleValidationMessage,
} = await import("../src/scheduleDateTime.ts");

test("предлагает ближайший будущий пятиминутный слот", () => {
  const now = new Date(2026, 8, 22, 10, 33, 0);

  assert.equal(nextScheduleValue(now), "2026-09-22T10:35");
  assert.equal(
    scheduleValidationMessage("2026-09-22T10:35", now.getTime()),
    "",
  );
});

test("оставляет запас, если ближайший слот наступит меньше чем через минуту", () => {
  const now = new Date(2026, 8, 22, 10, 34, 30);

  assert.equal(nextScheduleValue(now), "2026-09-22T10:40");
});

test("переводит серверное UTC-время в локальное значение формы", () => {
  const scheduledAt = "2026-09-22T07:35:00Z";

  assert.equal(localDateTimeValue(new Date(scheduledAt)), "2026-09-22T10:35");
  assert.equal(scheduleInputValue(scheduledAt), "2026-09-22T10:35");
});

test("отклоняет только действительно прошедшее локальное время", () => {
  const now = new Date(2026, 8, 22, 10, 36, 0);

  assert.equal(
    scheduleValidationMessage("2026-09-22T10:35", now.getTime()),
    "Выбранное время уже прошло.",
  );
});
