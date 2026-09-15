import { useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  CircleDot,
  Database,
  FileText,
  Info,
  LayoutDashboard,
  Radio,
  Settings,
} from "lucide-react";
import type { Target } from "../api";
import { projectLogo } from "../logoData";
import type { Section } from "../navigation";
import "../sidebarQueue.css";

type SidebarProps = {
  section: Section;
  targets: Target[];
  selectedQueueTargetId: number | null;
  onSectionChange: (section: Section) => void;
  onQueueTargetChange: (targetId: number | null) => void;
};

export function Sidebar({ section, targets, selectedQueueTargetId, onSectionChange, onQueueTargetChange }: SidebarProps) {
  const [queueOpen, setQueueOpen] = useState(section === "queue");
  const queueTargets = targets.filter((target) => target.is_active);

  useEffect(() => {
    if (section === "queue") setQueueOpen(true);
  }, [section]);

  function openQueue() {
    onQueueTargetChange(null);
    onSectionChange("queue");
    setQueueOpen((open) => section === "queue" ? !open : true);
  }

  function openQueueTarget(targetId: number) {
    onQueueTargetChange(targetId);
    onSectionChange("queue");
    setQueueOpen(true);
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
        <button onClick={() => onSectionChange("dashboard")} className={section === "dashboard" ? "active" : ""}><LayoutDashboard size={18} />Обзор</button>

        <div className={`queue-nav-group ${section === "queue" ? "active" : ""}`}>
          <button className={`queue-nav-parent ${section === "queue" ? "active" : ""}`} onClick={openQueue}>
            <FileText size={18} />
            <span>Очередь</span>
            {queueOpen ? <ChevronDown className="queue-nav-chevron" size={15} /> : <ChevronRight className="queue-nav-chevron" size={15} />}
          </button>

          {queueOpen && queueTargets.length > 0 && (
            <div className="queue-nav-children">
              {queueTargets.map((target) => (
                <button
                  key={target.target_id}
                  type="button"
                  className={`queue-nav-channel ${section === "queue" && selectedQueueTargetId === target.target_id ? "active" : ""}`}
                  title={target.name}
                  onClick={() => openQueueTarget(target.target_id)}
                >
                  <span className={`queue-nav-avatar ${target.icon_url ? "has-image" : ""}`}>
                    {target.icon_url ? <img src={target.icon_url} alt="" /> : <Radio size={13} />}
                  </span>
                  <span className="queue-nav-channel-name">{target.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <button onClick={() => onSectionChange("targets")} className={section === "targets" ? "active" : ""}><Radio size={18} />Каналы</button>
        <button onClick={() => onSectionChange("sources")} className={section === "sources" ? "active" : ""}><Database size={18} />Источники</button>
        <button onClick={() => onSectionChange("about")} className={section === "about" ? "active about-nav-button" : "about-nav-button"}><Info size={18} /><span>О проекте</span></button>
        <button onClick={() => onSectionChange("settings")} className={section === "settings" ? "active" : ""}><Settings size={18} />Настройки</button>
      </nav>

      <div className="sidebar-foot"><div className="system-state"><CircleDot size={14} /> Backend connected</div></div>
    </aside>
  );
}
