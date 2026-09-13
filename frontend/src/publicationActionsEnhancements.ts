export {};

function setReactInputValue(input: HTMLInputElement, value: string) {
  const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
  descriptor?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function findButton(root: ParentNode, text: string) {
  return Array.from(root.querySelectorAll<HTMLButtonElement>("button"))
    .find((button) => button.textContent?.trim().includes(text)) ?? null;
}

function waitForStatusAndNavigate(drawer: HTMLElement, expectedStatus: string, tabLabel: string) {
  const startedAt = Date.now();
  const timer = window.setInterval(() => {
    const status = drawer.querySelector<HTMLElement>(".editorial-status")?.textContent?.trim();
    if (status === expectedStatus) {
      window.clearInterval(timer);
      const tabButton = Array.from(document.querySelectorAll<HTMLButtonElement>(".editorial-tabs button"))
        .find((button) => button.textContent?.includes(tabLabel));
      if (tabButton) {
        tabButton.click();
        return;
      }
      drawer.querySelector<HTMLButtonElement>(".drawer-close")?.click();
      return;
    }

    if (!document.documentElement.contains(drawer) || Date.now() - startedAt > 15_000) {
      window.clearInterval(timer);
    }
  }, 100);
}

function enhanceApprovedDrawer(drawer: HTMLElement) {
  const schedulePanel = drawer.querySelector<HTMLElement>(".schedule-panel");
  const footer = drawer.querySelector<HTMLElement>(".drawer-footer");
  if (!schedulePanel || !footer) return;

  const originalScheduleInput = schedulePanel.querySelector<HTMLInputElement>('input[type="datetime-local"]');
  const originalScheduleButton = findButton(schedulePanel, "Поставить в очередь");
  const originalPublishButton = findButton(footer, "Опубликовать сейчас");
  if (!originalScheduleInput || !originalScheduleButton || !originalPublishButton) return;

  if (drawer.querySelector(".publication-choice-panel")) return;

  schedulePanel.classList.add("publication-controls-original");
  originalPublishButton.classList.add("publication-controls-original");

  const panel = document.createElement("section");
  panel.className = "publication-choice-panel";
  panel.innerHTML = `
    <div class="publication-choice-head">
      <div>
        <strong>Когда опубликовать?</strong>
        <span>Можно отправить пост сразу или назначить дату и время.</span>
      </div>
    </div>
    <div class="publication-choice-grid">
      <div class="publication-choice-card publication-choice-now">
        <div class="publication-choice-icon">↗</div>
        <div class="publication-choice-copy">
          <strong>Сейчас</strong>
          <span>Пост сразу отправится в MAX.</span>
        </div>
        <button type="button" class="primary publication-now-button">Опубликовать сейчас</button>
      </div>
      <div class="publication-choice-card publication-choice-later">
        <div class="publication-choice-icon">◷</div>
        <div class="publication-choice-copy">
          <strong>По расписанию</strong>
          <span>Система опубликует пост автоматически в указанное время.</span>
        </div>
        <label class="publication-date-label">
          <span>Дата и время</span>
          <input type="datetime-local" class="publication-date-input" />
        </label>
        <div class="publication-schedule-error" hidden></div>
        <button type="button" class="secondary publication-schedule-button">Запланировать</button>
      </div>
    </div>
  `;

  const dateInput = panel.querySelector<HTMLInputElement>(".publication-date-input")!;
  dateInput.value = originalScheduleInput.value;
  dateInput.min = new Date(Date.now() + 60_000).toISOString().slice(0, 16);

  const errorBox = panel.querySelector<HTMLElement>(".publication-schedule-error")!;
  const nowButton = panel.querySelector<HTMLButtonElement>(".publication-now-button")!;
  const scheduleButton = panel.querySelector<HTMLButtonElement>(".publication-schedule-button")!;

  nowButton.addEventListener("click", () => {
    originalPublishButton.click();
    waitForStatusAndNavigate(drawer, "Опубликован", "Архив");
  });

  scheduleButton.addEventListener("click", () => {
    errorBox.hidden = true;
    errorBox.textContent = "";
    const date = new Date(dateInput.value);
    if (!dateInput.value || Number.isNaN(date.getTime())) {
      errorBox.textContent = "Укажите дату и время публикации";
      errorBox.hidden = false;
      return;
    }
    if (date.getTime() <= Date.now()) {
      errorBox.textContent = "Время публикации должно быть в будущем";
      errorBox.hidden = false;
      return;
    }
    setReactInputValue(originalScheduleInput, dateInput.value);
    requestAnimationFrame(() => {
      originalScheduleButton.click();
      waitForStatusAndNavigate(drawer, "Запланирован", "Очередь публикаций");
    });
  });

  footer.before(panel);
}

function enhanceScheduledDrawer(drawer: HTMLElement) {
  const banner = drawer.querySelector<HTMLElement>(".scheduled-banner");
  if (!banner || banner.querySelector(".scheduled-auto-note")) return;

  const note = document.createElement("span");
  note.className = "scheduled-auto-note";
  note.textContent = "Система опубликует автоматически. При необходимости можно отправить раньше кнопкой «Опубликовать сейчас».";
  banner.append(note);
}

function scan() {
  document.querySelectorAll<HTMLElement>(".editorial-drawer").forEach((drawer) => {
    const status = drawer.querySelector<HTMLElement>(".editorial-status")?.textContent?.trim();
    if (status === "Согласован") enhanceApprovedDrawer(drawer);
    if (status === "Запланирован") enhanceScheduledDrawer(drawer);
  });
}

const observer = new MutationObserver(scan);
observer.observe(document.documentElement, { childList: true, subtree: true });
scan();
