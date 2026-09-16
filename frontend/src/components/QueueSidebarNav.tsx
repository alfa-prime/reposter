import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Radio } from "lucide-react";
import type { Target } from "../api";
import type { Section } from "../navigation";

type QueueSidebarNavProps = {
  section: Section;
  targets: Target[];
  selectedTargetId: number | null;
  onSectionChange: (section: Section) => void;
  onTargetChange: (targetId: number | null) => void;
};

export function QueueSidebarNav({
  section,
  targets,
  selectedTargetId,
  onSectionChange,
  onTargetChange,
}: QueueSidebarNavProps) {
  const [open, setOpen] = useState(section === "queue");
  const activeTargets = targets.filter((target) => target.is_active);

  useEffect(() => {
    if (section === "queue") setOpen(true);
  }, [section]);

  function openQueue() {
    onTargetChange(null);
    onSectionChange("queue");
    setOpen((current) => section === "queue" ? !current : true);
  }

  function openTarget(targetId: number) {
    onTargetChange(targetId);
    onSectionChange("queue");
    setOpen(true);
  }

  return (
    <div className={`queue-nav-group ${section === "queue" ? "active" : ""}`}>
      <button
        type="button"
        className={`queue-nav-parent ${section === "queue" ? "active" : ""}`}
        onClick={openQueue}
      >
        <FileText size={18} />
        <span>Очередь</span>
        {open ? (
          <ChevronDown className="queue-nav-chevron" size={15} />
        ) : (
          <ChevronRight className="queue-nav-chevron" size={15} />
        )}
      </button>

      {open && activeTargets.length > 0 && (
        <div className="queue-nav-children">
          {activeTargets.map((target) => (
            <button
              key={target.target_id}
              type="button"
              className={`queue-nav-channel ${section === "queue" && selectedTargetId === target.target_id ? "active" : ""}`}
              title={target.name}
              onClick={() => openTarget(target.target_id)}
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
  );
}
