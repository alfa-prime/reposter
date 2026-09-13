import { detectSourcePlatform } from "./api";

export {};

function installSourceWizard() {
  document.querySelectorAll<HTMLElement>(".modal-card").forEach((modal) => {
    const title = modal.querySelector("h2")?.textContent?.trim();
    if (title !== "Новый источник") return;
    if (modal.dataset.sourceWizardEnhanced === "true") return;
    modal.dataset.sourceWizardEnhanced = "true";

    const form = modal.querySelector<HTMLFormElement>("form.form-grid");
    const platformSelect = form?.querySelector<HTMLSelectElement>('select[name="platform"]');
    const urlInput = form?.querySelector<HTMLInputElement>('input[name="url"]');
    if (!form || !urlInput) return;

    platformSelect?.closest("label")?.remove();

    urlInput.placeholder = "https://vk.com/example";
    urlInput.setAttribute("inputmode", "url");

    const validate = () => {
      const value = urlInput.value.trim();
      if (!value) {
        urlInput.setCustomValidity("");
        return;
      }
      const platform = detectSourcePlatform(value);
      urlInput.setCustomValidity(
        platform
          ? ""
          : "Укажите ссылку на источник VK, Telegram или MAX, например https://vk.com/example",
      );
    };

    urlInput.addEventListener("input", validate);
    urlInput.addEventListener("blur", validate);
    form.addEventListener("submit", validate, { capture: true });
  });
}

const observer = new MutationObserver(installSourceWizard);
observer.observe(document.documentElement, { childList: true, subtree: true });
installSourceWizard();
