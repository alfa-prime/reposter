import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Radio } from "lucide-react";
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
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selectedChannel = value === null ? null : channels.find((channel) => channel.target_id === value) ?? null;
  const selectedLabel = selectedChannel
    ? `${selectedChannel.name}${selectedChannel.is_active === false ? " — отключён" : ""}`
    : "Все каналы";

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function choose(targetId: number | null) {
    onChange(targetId);
    setOpen(false);
  }

  return (
    <div className="queue-channel-filter" ref={rootRef}>
      <span className="queue-channel-filter-label">
        <Radio size={15} />
        Канал для работы
      </span>

      <div className="queue-channel-select">
        <button
          type="button"
          className={`queue-channel-select-trigger ${open ? "open" : ""}`}
          onClick={() => setOpen((current) => !current)}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label="Канал для работы"
        >
          <span>{selectedLabel}</span>
          <ChevronDown size={15} aria-hidden="true" />
        </button>

        {open && (
          <div className="queue-channel-options" role="listbox" aria-label="Канал для работы">
            <button
              type="button"
              role="option"
              aria-selected={value === null}
              className={value === null ? "selected" : ""}
              onClick={() => choose(null)}
            >
              <span>Все каналы</span>
              {value === null && <Check size={15} aria-hidden="true" />}
            </button>

            {channels.map((channel) => {
              const selected = value === channel.target_id;
              return (
                <button
                  key={channel.target_id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={selected ? "selected" : ""}
                  onClick={() => choose(channel.target_id)}
                >
                  <span>
                    {channel.name}
                    {channel.is_active === false && <small> — отключён</small>}
                  </span>
                  {selected && <Check size={15} aria-hidden="true" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
