import {
  CircleDot,
  Database,
  Info,
  Radio,
  Settings,
} from "lucide-react";
import type { Target } from "../api";
import { projectLogo } from "../logoData";
import type { Section } from "../navigation";
import "../sidebarQueue.css";
import { QueueSidebarNav } from "./QueueSidebarNav";

type SidebarProps = {
  section: Section;
  targets: Target[];
  selectedQueueTargetId: number | null;
  onSectionChange: (section: Section) => void;
  onQueueTargetChange: (targetId: number | null) => void;
};

export function Sidebar({ section, targets, selectedQueueTargetId, onSectionChange, onQueueTargetChange }: SidebarProps) {
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
        <button onClick={() => onSectionChange("settings")} className={section === "settings" ? "active" : ""}><Settings size={18} />Настройки</button>
      </nav>

      <div className="sidebar-foot"><div className="system-state"><CircleDot size={14} /> Backend connected</div></div>
    </aside>
  );
}
