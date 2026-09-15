import { CalendarClock } from "lucide-react";
import "./QueueSchedulePanel.css";

type QueueSchedulePanelProps = {
  value: string;
  busy: boolean;
  error?: string;
  onChange: (value: string) => void;
  onSchedule: () => void;
};

const hours = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
const minutes = Array.from({ length: 60 }, (_, index) => String(index).padStart(2, "0"));

function localDateValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function QueueSchedulePanel({ value, busy, error, onChange, onSchedule }: QueueSchedulePanelProps) {
  const [date = "", time = "00:00"] = value.split("T");
  const [hour = "00", minute = "00"] = time.split(":");
  const minDate = localDateValue(new Date());

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
            min={minDate}
            onChange={(event) => update(event.target.value, hour, minute)}
            aria-label="Дата публикации"
            required
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
        {error && <small className="schedule-validation-error" role="alert">{error}</small>}
      </label>
      <button className="primary" onClick={onSchedule} disabled={busy || !date || Boolean(error)}>
        <CalendarClock size={17}/>Поставить в очередь
      </button>
    </div>
  );
}
