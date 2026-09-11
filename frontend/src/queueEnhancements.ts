import React from "react";
import { createRoot, Root } from "react-dom/client";
import { QueueExperience } from "./QueueExperience";

let root: Root | null = null;
let host: HTMLDivElement | null = null;
let originalQueue: HTMLElement | null = null;
let scanScheduled = false;

function mountQueueExperience() {
  const queue = document.querySelector<HTMLElement>(".queue-layout");

  if (!queue) {
    if (root) root.unmount();
    root = null;
    host?.remove();
    host = null;
    if (originalQueue) originalQueue.style.display = "";
    originalQueue = null;
    return;
  }

  if (host && host.isConnected) return;

  originalQueue = queue;
  queue.style.display = "none";

  host = document.createElement("div");
  host.id = "queue-experience-root";
  queue.parentElement?.insertBefore(host, queue);

  root = createRoot(host);
  root.render(React.createElement(QueueExperience));
}

function scheduleScan() {
  if (scanScheduled) return;
  scanScheduled = true;
  requestAnimationFrame(() => {
    scanScheduled = false;
    mountQueueExperience();
  });
}

new MutationObserver(scheduleScan).observe(document.body, {
  childList: true,
  subtree: true,
});

window.addEventListener("popstate", scheduleScan);
scheduleScan();
