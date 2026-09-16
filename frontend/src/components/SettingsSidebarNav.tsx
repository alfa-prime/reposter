import { useEffect, useState } from "react";
import { CalendarClock, ChevronDown, ChevronRight, ScrollText, Settings } from "lucide-react";
import type { Section } from "../navigation";

type Props = {
  section: Section;
  onSectionChange: (section: Section) => void;
};

export function SettingsSidebarNav({ section, onSectionChange }: Props) {
  const active = section === "scheduler" || section === "scheduler_logs";
  const [open, setOpen] = useState(active);

  useEffect(() => { if (active) setOpen(true); }, [active]);

  function openSettings() {
    if (!active) onSectionChange("scheduler");
    setOpen((current) => active ? !current : true);
  }

  return (
    <div className={`queue-nav-group settings-nav-group ${active ? "active" : ""}`}>
      <button type="button" className={`queue-nav-parent ${active ? "active" : ""}`} onClick={openSettings}>
        <Settings size={18} /><span>Настройки</span>
        {open ? <ChevronDown className="queue-nav-chevron" size={15} /> : <ChevronRight className="queue-nav-chevron" size={15} />}
      </button>
      {open && (
        <div className="queue-nav-children settings-nav-children">
          <button type="button" className={`queue-nav-channel ${section === "scheduler" ? "active" : ""}`} onClick={() => onSectionChange("scheduler")}>
            <CalendarClock size={15} /><span className="queue-nav-channel-name">Расписание планировщика</span>
          </button>
          <button type="button" className={`queue-nav-channel ${section === "scheduler_logs" ? "active" : ""}`} onClick={() => onSectionChange("scheduler_logs")}>
            <ScrollText size={15} /><span className="queue-nav-channel-name">Журнал планировщика</span>
          </button>
        </div>
      )}
    </div>
  );
}
