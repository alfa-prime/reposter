import { projectLogo } from "./logoData";

function applyBrandLogo() {
  const mark = document.querySelector<HTMLElement>(".brand-mark");
  if (!mark || mark.dataset.logoApplied === "true") return;

  mark.dataset.logoApplied = "true";
  mark.classList.add("brand-portrait");
  mark.replaceChildren();

  const image = document.createElement("img");
  image.src = projectLogo;
  image.alt = "Дядя Влад";
  image.decoding = "async";
  mark.appendChild(image);
}

applyBrandLogo();

const observer = new MutationObserver(() => applyBrandLogo());
observer.observe(document.body, { childList: true, subtree: true });
