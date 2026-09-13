import { detectTargetPlatform } from "./api";

const ENHANCED_ATTR = "data-target-wizard-enhanced";

function labelByField(form: HTMLFormElement, fieldName: string): HTMLLabelElement | null {
  const field = form.elements.namedItem(fieldName);
  return field instanceof HTMLElement ? field.closest("label") : null;
}

function enhanceTargetForm(form: HTMLFormElement) {
  if (form.getAttribute(ENHANCED_ATTR) === "true") return;
  form.setAttribute(ENHANCED_ATTR, "true");

  const platformCandidate = form.elements.namedItem("platform") as HTMLSelectElement | null;
  const externalIdCandidate = form.elements.namedItem("external_id") as HTMLInputElement | null;
  const urlCandidate = form.elements.namedItem("url") as HTMLInputElement | null;
  const submitCandidate = form.querySelector<HTMLButtonElement>('button[type="submit"], button.primary');
  if (!platformCandidate || !externalIdCandidate || !urlCandidate || !submitCandidate) return;

  const platform = platformCandidate;
  const externalId = externalIdCandidate;
  const url = urlCandidate;
  const submit = submitCandidate;

  const platformLabel = labelByField(form, "platform");
  const externalIdLabel = labelByField(form, "external_id");
  const urlLabel = labelByField(form, "url");

  platform.required = false;
  externalId.required = false;
  platformLabel?.classList.add("target-auto-hidden");
  externalIdLabel?.classList.add("target-auto-hidden");

  url.required = true;
  url.placeholder = "https://max.ru/...";
  urlLabel?.classList.add("wide");
  if (urlLabel) {
    const small = urlLabel.querySelector("small");
    if (small) small.remove();
    const textNode = Array.from(urlLabel.childNodes).find((node) => node.nodeType === Node.TEXT_NODE);
    if (textNode) textNode.textContent = "Ссылка ";
    if (!urlLabel.querySelector("b")) {
      const required = document.createElement("b");
      required.textContent = "*";
      urlLabel.insertBefore(required, urlLabel.firstElementChild);
    }
  }

  const panel = document.createElement("div");
  panel.className = "target-connect-panel wide";
  panel.innerHTML = `
    <div class="target-platform-state">Вставьте ссылку — платформа определится автоматически</div>
    <div class="target-connect-help"></div>
  `;
  submit.before(panel);

  const state = panel.querySelector<HTMLElement>(".target-platform-state")!;
  const help = panel.querySelector<HTMLElement>(".target-connect-help")!;

  function refresh() {
    const detected = detectTargetPlatform(url.value);
    if (!detected) {
      platform.value = "max";
      externalId.value = "";
      state.textContent = url.value.trim()
        ? "Не удалось распознать ссылку. Поддерживаются MAX, Telegram и VK."
        : "Вставьте ссылку — платформа определится автоматически";
      state.className = `target-platform-state${url.value.trim() ? " error" : ""}`;
      help.innerHTML = "";
      submit.textContent = "Добавить канал";
      return;
    }

    platform.value = detected;
    externalId.value = "auto";
    const names = { max: "MAX", telegram: "Telegram", vk: "VK" } as const;
    state.textContent = `${names[detected]} определён автоматически`;
    state.className = "target-platform-state ok";

    if (detected === "max") {
      help.innerHTML = `
        <strong>Подключение MAX</strong>
        <ol>
          <li>Добавьте бота <code>Neuro_writer_51</code> в подписчики канала.</li>
          <li>Затем назначьте этого бота администратором канала.</li>
          <li>После этого нажмите «Проверить и добавить канал».</li>
        </ol>
        <p>Если бот уже был подключён раньше, удалите его из канала и добавьте заново, чтобы MAX прислал событие подключения.</p>
      `;
      submit.textContent = "Проверить и добавить канал";
    } else {
      help.innerHTML = "<p>Платформа и идентификатор канала будут определены по ссылке автоматически.</p>";
      submit.textContent = "Добавить канал";
    }
  }

  url.addEventListener("input", refresh);
  url.addEventListener("change", refresh);
  refresh();
}

function scanTargetModal() {
  document.querySelectorAll<HTMLFormElement>(".modal-card form.form-grid").forEach((form) => {
    const modal = form.closest(".modal-card");
    if (modal?.querySelector("h2")?.textContent?.trim() === "Новый канал") {
      enhanceTargetForm(form);
    }
  });
}

const observer = new MutationObserver(scanTargetModal);
observer.observe(document.documentElement, { childList: true, subtree: true });
scanTargetModal();
