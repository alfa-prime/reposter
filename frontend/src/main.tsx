import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { ThemeToggle } from "./ThemeToggle";
import "./styles.css";
import "./ux.css";
import "./theme.css";
import "./queueEnhancements.css";
import "./polish.css";
import "./brand.css";
import "./mediaControls.css";
import "./queueExperiencePatch.css";
import "./targetComponents.css";
import "./videoEnhancements.css";
import "./publicationActionsEnhancements.css";
import "./aboutEnhancements.css";
import "./sourceComponents.css";
import "./queueEnhancements";
import "./brandEnhancements";
import "./signatureEnhancements";
import "./videoEnhancements";
import "./publicationActionsEnhancements";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeToggle />
    <App />
  </React.StrictMode>,
);
