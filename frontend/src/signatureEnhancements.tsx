import React from "react";
import { createRoot, Root } from "react-dom/client";
import { api } from "./api";
import { PostSignatureSection } from "./components/SignatureSections";

let postRoot: Root | null = null;
let postHost: HTMLElement | null = null;
let scanning = false;
let postMounting = false;

function removeDuplicateHosts(container: HTMLElement) {
  const hosts = Array.from(
    container.querySelectorAll<HTMLElement>('.signature-enhancement-host[data-signature-kind="post"]'),
  );
  if (hosts.length <= 1) return;
  hosts.slice(1).forEach((host) => host.remove());
}

async function mountPostSignature() {
  const drawer = document.querySelector<HTMLElement>(".editorial-drawer");
  const sourceLink = drawer?.querySelector<HTMLAnchorElement>(".drawer-source-row a")?.href;

  if (drawer && sourceLink) {
    removeDuplicateHosts(drawer);
    if (!postMounting && (!postHost || !postHost.isConnected || postHost.dataset.sourceUrl !== sourceLink)) {
      postMounting = true;
      try {
        postRoot?.unmount();
        postHost?.remove();
        postHost = null;
        postRoot = null;

        const items = await api.queue();
        if (!drawer.isConnected) return;
        const item = items.find(
          (candidate) => candidate.source_url && new URL(candidate.source_url, location.origin).href === sourceLink,
        );
        if (!item) return;

        const host = document.createElement("div");
        host.className = "signature-enhancement-host";
        host.dataset.signatureKind = "post";
        host.dataset.sourceUrl = sourceLink;
        const textSection = drawer.querySelector(".drawer-text-section");
        textSection?.insertAdjacentElement("afterend", host);
        postHost = host;
        postRoot = createRoot(host);
        postRoot.render(<PostSignatureSection item={item} />);
      } finally {
        postMounting = false;
      }
    }
  } else if (postHost && !postMounting) {
    postRoot?.unmount();
    postHost.remove();
    postHost = null;
    postRoot = null;
  }
}

function scheduleMount() {
  if (scanning) return;
  scanning = true;
  requestAnimationFrame(() => {
    scanning = false;
    void mountPostSignature();
  });
}

new MutationObserver(scheduleMount).observe(document.body, { childList: true, subtree: true });
scheduleMount();
