import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { initializeTheme } from "./theme";
import "./styles.css";
import "./ux.css";
import "./theme.css";
import "./polish.css";
import "./brand.css";
import "./mediaControls.css";
import "./targetComponents.css";
import "./sourceComponents.css";
import "./auth.css";
import "./userMenu.css";

initializeTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
