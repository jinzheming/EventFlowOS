import { Link2, MapPin } from 'lucide-react';
import type { EventFormat } from '../api/client';
import { eventFormatLabels } from '../lib/labels';

export type EventLocationDraft = {
  event_format: EventFormat | '';
  event_location: string;
  event_url: string;
};

const eventFormatOptions: Array<{ value: EventFormat | ''; label: string }> = [
  { value: '', label: '未设置' },
  { value: 'online', label: eventFormatLabels.online },
  { value: 'offline', label: eventFormatLabels.offline },
  { value: 'hybrid', label: eventFormatLabels.hybrid },
];

export function EventFormatFields({
  value,
  onChange,
}: {
  value: EventLocationDraft;
  onChange: (patch: Partial<EventLocationDraft>) => void;
}) {
  const isOnline = value.event_format === 'online' || value.event_format === 'hybrid';
  const isOffline = value.event_format === 'offline' || value.event_format === 'hybrid';

  return (
    <section className="event-format-box" aria-label="活动形式">
      <div className="event-format-title">
        <MapPin size={16} /> 活动形式
      </div>
      <div className="segmented-control event-format-options">
        {eventFormatOptions.map((option) => (
          <button
            className={value.event_format === option.value ? 'chip active' : 'chip'}
            type="button"
            key={option.value || 'none'}
            onClick={() => onChange({ event_format: option.value })}
          >
            {option.label}
          </button>
        ))}
      </div>
      {isOnline && (
        <label>
          <span className="event-format-label">
            <Link2 size={14} /> 线上链接
          </span>
          <input
            type="url"
            placeholder="https://meeting.example.com/..."
            value={value.event_url}
            onChange={(event) => onChange({ event_url: event.target.value })}
          />
        </label>
      )}
      {isOffline && (
        <label>
          <span className="event-format-label">
            <MapPin size={14} /> 线下地点
          </span>
          <input
            placeholder="会议室、门店或地址"
            value={value.event_location}
            onChange={(event) => onChange({ event_location: event.target.value })}
          />
        </label>
      )}
      {!value.event_format && <p className="hint">需要记录会议或约定地点时，可选择线上、线下或混合形式。</p>}
    </section>
  );
}
