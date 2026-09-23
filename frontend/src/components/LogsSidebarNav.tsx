import { useEffect, useState } from "react";
import { CalendarClock, ChevronDown, ChevronRight, ScrollText } from "lucide-react";
import type { Section } from "../navigation";

type Props = {
  section: Section;
  onSectionChange: (section: Section) => void;
};

export function LogsSidebarNav({ section, onSectionChange }: Props) {
  const active = section === "logs";
  const [open, setOpen] = useState(active);

  useEffect(() => {
    if (active) setOpen(true);
  }, [active]);

  return (
    <div className={`queue-nav-group logs-nav-group ${active ? "active" : ""}`}>
      <button
        type="button"
        className={`queue-nav-parent ${active ? "active" : ""}`}
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <ScrollText size={18} /><span>Журналы</span>
        {open ? <ChevronDown className="queue-nav-chevron" size={15} /> : <ChevronRight className="queue-nav-chevron" size={15} />}
      </button>
      {open && (
        <div className="queue-nav-children logs-nav-children">
          <button
            type="button"
            className={`queue-nav-channel ${active ? "active" : ""}`}
            onClick={() => onSectionChange("logs")}
          >
            <CalendarClock size={15} />
            <span className="queue-nav-channel-name">Журнал планировщика</span>
          </button>
        </div>
      )}
    </div>
  );
}
