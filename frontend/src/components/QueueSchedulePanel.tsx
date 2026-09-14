import { CalendarClock } from "lucide-react";
import "./QueueSchedulePanel.css";

type QueueSchedulePanelProps = {
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSchedule: () => void;
};

const hours = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
const minutes = Array.from({ length: 60 }, (_, index) => String(index).padStart(2, "0"));

export function QueueSchedulePanel({ value, busy, onChange, onSchedule }: QueueSchedulePanelProps) {
  const [date = "", time = "00:00"] = value.split("T");
  const [hour = "00", minute = "00"] = time.split(":");

  function update(nextDate: string, nextHour: string, nextMinute: string) {
    onChange(`${nextDate}T${nextHour}:${nextMinute}`);
  }

  return (
    <div className="schedule-panel">
      <label>
        Дата и время публикации
        <div className="schedule-datetime-controls">
          <input
            type="date"
            value={date}
            onChange={(event) => update(event.target.value, hour, minute)}
            aria-label="Дата публикации"
          />
          <div className="schedule-time-controls" aria-label="Время публикации в 24-часовом формате">
            <select
              value={hour}
              onChange={(event) => update(date, event.target.value, minute)}
              aria-label="Часы"
            >
              {hours.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <span>:</span>
            <select
              value={minute}
              onChange={(event) => update(date, hour, event.target.value)}
              aria-label="Минуты"
            >
              {minutes.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
        </div>
      </label>
      <button className="primary" onClick={onSchedule} disabled={busy}>
        <CalendarClock size={17}/>Поставить в очередь
      </button>
    </div>
  );
}
