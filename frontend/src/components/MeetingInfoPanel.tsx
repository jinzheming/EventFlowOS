import { ExternalLink, Video } from 'lucide-react';
import { Item } from '../api/client';

export function MeetingInfoPanel({ item }: { item: Item }) {
  const meta = objectValue(item.source_context?.meeting_meta);
  if (!meta) return null;
  const joinUrl = stringValue(meta.join_url);
  const meetingId = stringValue(meta.meeting_id);
  const meetingCode = stringValue(meta.meeting_code);
  const parser = stringValue(item.source_context?.parser);
  const confidence = numberValue(item.source_context?.confidence);
  const tmeet = objectValue(item.source_context?.tmeet_lookup);
  const tmeetStatus = stringValue(tmeet?.status);
  if (!joinUrl && !meetingId && !meetingCode) return null;

  return (
    <section className="meeting-info-panel" aria-label="会议来源信息">
      <div className="meeting-info-title">
        <Video size={16} /> 腾讯会议
      </div>
      <div className="meeting-info-grid">
        {joinUrl && (
          <a href={joinUrl} target="_blank" rel="noreferrer">
            入会链接 <ExternalLink size={13} />
          </a>
        )}
        {meetingId && <span>会议号：{meetingId}</span>}
        {meetingCode && <span>密码：{meetingCode}</span>}
      </div>
      {(parser || confidence !== null || tmeetStatus) && (
        <p>
          来源：{parser || 'agent'}
          {confidence !== null ? ` · 置信度 ${Math.round(confidence * 100)}%` : ''}
          {tmeetStatus ? ` · tmeet ${tmeetStatus}` : ''}
        </p>
      )}
    </section>
  );
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value : '';
}

function numberValue(value: unknown) {
  return typeof value === 'number' ? value : null;
}
