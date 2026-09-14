import {
  CircleDot,
  Database,
  FileText,
  Info,
  LayoutDashboard,
  Radio,
} from "lucide-react";
import { projectLogo } from "../logoData";
import type { Section } from "../navigation";

type SidebarProps = {
  section: Section;
  onSectionChange: (section: Section) => void;
};

export function Sidebar({ section, onSectionChange }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark brand-portrait">
          <img src={projectLogo} alt="Дядя Влад" decoding="async" />
        </div>
        <div><strong>Дядя Влад</strong><span>читает новости</span></div>
      </div>

      <nav>
        <button onClick={() => onSectionChange("dashboard")} className={section === "dashboard" ? "active" : ""}><LayoutDashboard size={18} />Обзор</button>
        <button onClick={() => onSectionChange("queue")} className={section === "queue" ? "active" : ""}><FileText size={18} />Очередь</button>
        <button onClick={() => onSectionChange("targets")} className={section === "targets" ? "active" : ""}><Radio size={18} />Каналы</button>
        <button onClick={() => onSectionChange("sources")} className={section === "sources" ? "active" : ""}><Database size={18} />Источники</button>
        <button onClick={() => onSectionChange("about")} className={section === "about" ? "active about-nav-button" : "about-nav-button"}><Info size={18} /><span>О проекте</span></button>
      </nav>

      <div className="sidebar-foot"><div className="system-state"><CircleDot size={14} /> Backend connected</div></div>
    </aside>
  );
}
