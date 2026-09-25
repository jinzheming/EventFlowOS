import { Check, ExternalLink, Link2, MapPin, Search } from 'lucide-react';
import { useState } from 'react';
import { api, type EventFormat, type LocationCandidate, type MeetingParsePreview } from '../api/client';
import { formatScheduleTime } from '../lib/dates';
import { eventFormatLabels } from '../lib/labels';

export type EventLocationDraft = {
  event_format: EventFormat | '';
  event_location: string;
  event_url: string;
  location_name?: string;
  location_address?: string;
  location_provider?: string;
  location_poi_id?: string;
  location_latitude?: number | null;
  location_longitude?: number | null;
  location_confidence?: number | null;
};

const eventFormatOptions: Array<{ value: EventFormat | ''; label: string }> = [
  { value: '', label: '未设置' },
  { value: 'online', label: eventFormatLabels.online },
  { value: 'offline', label: eventFormatLabels.offline },
];

export function EventFormatFields({
  value,
  onChange,
  onMeetingParsed,
  timezone,
}: {
  value: EventLocationDraft;
  onChange: (patch: Partial<EventLocationDraft>) => void;
  onMeetingParsed?: (preview: MeetingParsePreview) => void;
  timezone?: string;
}) {
  const isOnline = value.event_format === 'online';
  const isOffline = value.event_format === 'offline';
  const [meetingPreview, setMeetingPreview] = useState<MeetingParsePreview | null>(null);
  const [meetingRawText, setMeetingRawText] = useState('');
  const [locationCandidates, setLocationCandidates] = useState<LocationCandidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function parseMeeting() {
    if (!meetingRawText.trim()) return;
    setBusy(true); setError(null);
    try {
      const preview = await api.parseMeetingInput({ raw_text: meetingRawText, enrich_tmeet: true, timezone });
      setMeetingPreview(preview);
      if (!preview.title && !preview.join_url && !preview.meeting_id && !preview.meeting_code && !preview.start_at && !preview.due_at && !preview.estimated_minutes) {
        setError('未能识别出会议字段；原文仍保留，可继续手动填写。');
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '会议解析失败');
    } finally { setBusy(false); }
  }

  function applyMeetingSuggestions() {
    if (!meetingPreview) return;
    onChange({
      event_format: 'online',
      ...(meetingPreview.join_url && !value.event_url.trim() ? { event_url: meetingPreview.join_url } : {}),
    });
    onMeetingParsed?.(meetingPreview);
  }

  async function resolveLocation() {
    if (!value.event_location.trim()) return;
    setBusy(true); setError(null);
    try {
      const result = await api.resolveLocation({ query: value.event_location, search_poi: true });
      setLocationCandidates(result.candidates);
      if (!result.candidates.length && result.status !== 'ok') setError(result.error || '地图服务未启用');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '地址解析失败');
    } finally { setBusy(false); }
  }

  function selectLocation(candidate: LocationCandidate) {
    onChange({
      event_format: 'offline', event_location: candidate.address || candidate.name,
      location_name: candidate.name, location_address: candidate.address,
      location_provider: candidate.provider, location_poi_id: candidate.poi_id || '',
      location_latitude: candidate.latitude, location_longitude: candidate.longitude,
      location_confidence: candidate.confidence,
    });
    setLocationCandidates([]);
  }

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
            onClick={() => onChange({ event_format: option.value, event_url: option.value === 'online' ? value.event_url : '', event_location: option.value === 'offline' ? value.event_location : '' })}
          >
            {option.label}
          </button>
        ))}
      </div>
      {isOnline && (
        <div className="event-format-inputs">
          <label>
            <span className="event-format-label"><Link2 size={14} /> 会议邀请原文或链接</span>
            <textarea rows={4} placeholder="粘贴会议通知或链接；解析不会覆盖原文" value={meetingRawText} onChange={(event) => { setMeetingRawText(event.target.value); setMeetingPreview(null); setError(null); }} />
          </label>
          <button className="secondary-button" type="button" onClick={() => void parseMeeting()} disabled={busy || !meetingRawText.trim()}>
            <Search size={14} /> {busy ? '解析中…' : '解析会议'}
          </button>
          <label>
            线上加入链接
            <input type="url" placeholder="https://..." value={value.event_url} onChange={(event) => onChange({ event_url: event.target.value })} />
          </label>
          {meetingPreview && (
            <div className="meeting-parse-preview" aria-live="polite">
              <p className="hint">识别候选（置信度 {Math.round(meetingPreview.confidence * 100)}%）：{meetingPreview.title || '未识别主题'}；{meetingPreview.start_at ? `${formatScheduleTime(meetingPreview.start_at)} 至 ${meetingPreview.due_at ? formatScheduleTime(meetingPreview.due_at) : '待补充'}` : '时间待补充'}。{meetingPreview.missing_fields.length ? `待确认：${meetingPreview.missing_fields.join('、')}` : ''}{meetingPreview.tmeet_lookup && typeof meetingPreview.tmeet_lookup.status === 'string' ? `；tmeet：${meetingPreview.tmeet_lookup.status}` : ''}</p>
              {meetingPreview.join_url && <p className="hint">候选链接：{meetingPreview.join_url}</p>}
              <button className="secondary-button" type="button" onClick={applyMeetingSuggestions} disabled={!meetingPreview.title && !meetingPreview.join_url && !meetingPreview.start_at && !meetingPreview.due_at && !meetingPreview.estimated_minutes}>
                <Check size={14} /> 将识别结果填入空字段
              </button>
            </div>
          )}
        </div>
      )}
      {isOffline && (
        <div className="event-format-inputs">
          <label>
            <span className="event-format-label"><MapPin size={14} /> 线下地点</span>
            <input
              placeholder="会议室、门店或地址"
              value={value.event_location}
              onChange={(event) => {
                const query = event.target.value;
                setLocationCandidates([]);
                if (query === value.location_address || query === value.event_location) {
                  onChange({ event_location: query });
                } else {
                  onChange({
                    event_location: query,
                    location_name: '', location_address: '', location_provider: '', location_poi_id: '',
                    location_latitude: null, location_longitude: null, location_confidence: null,
                  });
                }
              }}
            />
          </label>
          <button className="secondary-button" type="button" onClick={() => void resolveLocation()} disabled={busy || !value.event_location.trim()}>
            <Search size={14} /> {busy ? '搜索中…' : '搜索地图地点'}
          </button>
          {locationCandidates.map((candidate) => (
            <button className="location-candidate" type="button" key={`${candidate.poi_id || candidate.name}-${candidate.latitude}`} onClick={() => selectLocation(candidate)}>
              <strong>{candidate.name}</strong><span>{candidate.address}</span>
            </button>
          ))}
          {value.location_name && (
            <div className="location-selection">
              <span>{value.location_name}{value.location_provider ? ` · ${value.location_provider}` : ''}</span>
              {value.location_confidence != null && <span>匹配度 {Math.round(value.location_confidence * 100)}%</span>}
              {value.location_latitude != null && value.location_longitude != null && (
                <a href={`https://uri.amap.com/marker?position=${value.location_longitude},${value.location_latitude}&name=${encodeURIComponent(value.location_name)}`} target="_blank" rel="noreferrer">
                  查看地图 <ExternalLink size={13} />
                </a>
              )}
            </div>
          )}
        </div>
      )}
      {error && <p className="hint error-text">{error}</p>}
      {!value.event_format && <p className="hint">需要记录会议或约定地点时，可选择线上或线下形式。</p>}
    </section>
  );
}
