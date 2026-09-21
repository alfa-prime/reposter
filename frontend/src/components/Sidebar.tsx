import { useEffect, useState } from "react";
import {
  Database,
  Info,
  Moon,
  Radio,
  Sun,
} from "lucide-react";
import type { Target } from "../api";
import { projectLogo } from "../logoData";
import type { Section } from "../navigation";
import { applyTheme, getInitialTheme, Theme } from "../theme";
import "../sidebarQueue.css";
import { QueueSidebarNav } from "./QueueSidebarNav";
import { SettingsSidebarNav } from "./SettingsSidebarNav";
import { UserMenu } from "./UserMenu";

type SidebarProps = {
  section: Section;
  targets: Target[];
  selectedQueueTargetId: number | null;
  onSectionChange: (section: Section) => void;
  onQueueTargetChange: (targetId: number | null) => void;
};

export function Sidebar({ section, targets, selectedQueueTargetId, onSectionChange, onQueueTargetChange }: SidebarProps) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const isLight = theme === "light";

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function toggleTheme() {
    setTheme(isLight ? "dark" : "light");
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark brand-portrait">
          <img src={projectLogo} alt="Дядя Влад" decoding="async" />
        </div>
        <div><strong>Дядя Влад</strong><span>читает новости</span></div>
      </div>

      <nav>
        <QueueSidebarNav
          section={section}
          targets={targets}
          selectedTargetId={selectedQueueTargetId}
          onSectionChange={onSectionChange}
          onTargetChange={onQueueTargetChange}
        />

        <button onClick={() => onSectionChange("targets")} className={section === "targets" ? "active" : ""}><Radio size={18} />Каналы</button>
        <button onClick={() => onSectionChange("sources")} className={section === "sources" ? "active" : ""}><Database size={18} />Источники</button>
        <button onClick={() => onSectionChange("about")} className={section === "about" ? "active about-nav-button" : "about-nav-button"}><Info size={18} /><span>О проекте</span></button>
        <SettingsSidebarNav section={section} onSectionChange={onSectionChange} />
      </nav>

      <div className="sidebar-foot">
        <UserMenu />
        <div className="sidebar-theme-row">
          <span className="sidebar-theme-label">
            {isLight ? <Sun size={15} /> : <Moon size={15} />}
            {isLight ? "Светлая тема" : "Тёмная тема"}
          </span>
          <button
            className="theme-switch"
            type="button"
            onClick={toggleTheme}
            aria-label={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
            aria-pressed={isLight}
          >
            <span className="theme-switch-track" aria-hidden="true">
              <Sun size={13} className="theme-switch-sun" />
              <Moon size={13} className="theme-switch-moon" />
              <span className="theme-switch-thumb" />
            </span>
          </button>
        </div>

        <button
          className="sidebar-theme-compact"
          type="button"
          onClick={toggleTheme}
          title={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
          aria-label={isLight ? "Включить тёмную тему" : "Включить светлую тему"}
        >
          {isLight ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </div>
    </aside>
  );
}
