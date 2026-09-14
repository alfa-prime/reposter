import { Radio } from "lucide-react";
import "./QueueChannelFilter.css";

export type QueueChannelOption = {
  target_id: number;
  name: string;
  is_active?: boolean;
};

type QueueChannelFilterProps = {
  channels: QueueChannelOption[];
  value: number | null;
  onChange: (targetId: number | null) => void;
};

export function QueueChannelFilter({ channels, value, onChange }: QueueChannelFilterProps) {
  return (
    <label className="queue-channel-filter">
      <span className="queue-channel-filter-label">
        <Radio size={15} />
        Канал для работы
      </span>
      <select
        value={value === null ? "all" : String(value)}
        onChange={(event) => {
          const next = event.target.value;
          onChange(next === "all" ? null : Number(next));
        }}
        aria-label="Канал для работы"
      >
        <option value="all">Все каналы</option>
        {channels.map((channel) => (
          <option key={channel.target_id} value={channel.target_id}>
            {channel.name}{channel.is_active === false ? " — отключён" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
