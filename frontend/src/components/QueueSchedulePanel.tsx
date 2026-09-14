import { CalendarClock } from "lucide-react";

type QueueSchedulePanelProps = {
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSchedule: () => void;
};

export function QueueSchedulePanel({ value, busy, onChange, onSchedule }: QueueSchedulePanelProps) {
  return (
    <div className="schedule-panel">
      <label>
        Дата и время публикации
        <input
          type="datetime-local"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      <button className="primary" onClick={onSchedule} disabled={busy}>
        <CalendarClock size={17}/>Поставить в очередь
      </button>
    </div>
  );
}
