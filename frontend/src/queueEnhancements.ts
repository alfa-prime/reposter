let lightbox: HTMLDivElement | null = null;

function closeLightbox() {
  lightbox?.remove();
  lightbox = null;
  document.body.classList.remove("lightbox-open");
}

function openLightbox(image: HTMLImageElement) {
  closeLightbox();

  const images = Array.from(
    image.closest(".photo-strip")?.querySelectorAll<HTMLImageElement>("img") ?? [],
  );
  let index = Math.max(0, images.indexOf(image));

  const overlay = document.createElement("div");
  overlay.className = "media-lightbox";
  overlay.innerHTML = `
    <button class="media-lightbox-close" type="button" aria-label="Закрыть">×</button>
    <button class="media-lightbox-nav media-lightbox-prev" type="button" aria-label="Предыдущее фото">‹</button>
    <figure>
      <img alt="Фотография поста" />
      <figcaption></figcaption>
    </figure>
    <button class="media-lightbox-nav media-lightbox-next" type="button" aria-label="Следующее фото">›</button>
  `;

  const preview = overlay.querySelector<HTMLImageElement>("figure img")!;
  const caption = overlay.querySelector<HTMLElement>("figcaption")!;
  const prev = overlay.querySelector<HTMLButtonElement>(".media-lightbox-prev")!;
  const next = overlay.querySelector<HTMLButtonElement>(".media-lightbox-next")!;

  const render = () => {
    const current = images[index];
    preview.src = current.src;
    caption.textContent = images.length > 1 ? `${index + 1} из ${images.length}` : "";
    prev.hidden = images.length < 2;
    next.hidden = images.length < 2;
  };

  prev.addEventListener("click", (event) => {
    event.stopPropagation();
    index = (index - 1 + images.length) % images.length;
    render();
  });
  next.addEventListener("click", (event) => {
    event.stopPropagation();
    index = (index + 1) % images.length;
    render();
  });
  overlay.querySelector(".media-lightbox-close")?.addEventListener("click", closeLightbox);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeLightbox();
  });

  render();
  document.body.appendChild(overlay);
  document.body.classList.add("lightbox-open");
  lightbox = overlay;
}

function markCollapsibleSourceText() {
  document.querySelectorAll<HTMLElement>(".original-text").forEach((element) => {
    element.classList.remove("is-collapsible", "expanded");
    if (element.scrollHeight > 132) {
      element.classList.add("is-collapsible");
      element.setAttribute("role", "button");
      element.setAttribute("tabindex", "0");
      element.setAttribute("aria-expanded", "false");
      element.setAttribute("title", "Показать исходный текст полностью");
    }
  });
}

function toggleSourceText(element: HTMLElement) {
  if (!element.classList.contains("is-collapsible")) return;
  const expanded = element.classList.toggle("expanded");
  element.setAttribute("aria-expanded", String(expanded));
  element.setAttribute("title", expanded ? "Свернуть исходный текст" : "Показать исходный текст полностью");
}

let scanScheduled = false;
function scheduleScan() {
  if (scanScheduled) return;
  scanScheduled = true;
  requestAnimationFrame(() => {
    scanScheduled = false;
    markCollapsibleSourceText();
  });
}

document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const image = target.closest<HTMLImageElement>(".photo-strip img");
  if (image) {
    openLightbox(image);
    return;
  }

  const sourceText = target.closest<HTMLElement>(".original-text.is-collapsible");
  if (sourceText) toggleSourceText(sourceText);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeLightbox();

  const target = event.target as HTMLElement;
  if ((event.key === "Enter" || event.key === " ") && target.matches(".original-text.is-collapsible")) {
    event.preventDefault();
    toggleSourceText(target);
  }
});

new MutationObserver(scheduleScan).observe(document.body, {
  childList: true,
  subtree: true,
});

window.addEventListener("resize", scheduleScan);
scheduleScan();
