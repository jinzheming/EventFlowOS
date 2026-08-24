import { DragEvent, PointerEvent as ReactPointerEvent, useRef, useState } from 'react';
import { CalendarEvent } from '../api/client';
import { formatScheduleTime, todayString } from '../lib/dates';
import { HOUR_HEIGHT, WEEKDAY_LABELS, WEEK_END_HOUR, WEEK_START_HOUR, WeekDayBucket, eventDurationMinutes, snap15 } from '../lib/week';

const HOURS = Array.from({ length: WEEK_END_HOUR - WEEK_START_HOUR }, (_, index) => WEEK_START_HOUR + index);

function pad2(value: number) {
  return String(value).padStart(2, '0');
}

type DragPreview = { x: number; y: number; label: string } | null;

export function WeekGrid({
  dates,
  buckets,
  onOpenItem,
  onDropItem,
  onResizeItem,
  onResizeStartItem,
  dragEnabled = true,
}: {
  dates: string[];
  buckets: Map<string, WeekDayBucket>;
  onOpenItem: (sourceId: string) => void;
  /** hour+minute give the 15-minute-aligned drop target; hour null means all-day. */
  onDropItem: (sourceId: string, date: string, hour: number | null, minute: number) => void;
  onResizeItem: (sourceId: string, durationMinutes: number) => void;
  /** new start time as minutes since midnight (15-min aligned). */
  onResizeStartItem: (sourceId: string, startMinutes: number) => void;
  dragEnabled?: boolean;
}) {
  const today = todayString();
  const resizingRef = useRef(false);
  const [preview, setPreview] = useState<DragPreview>(null);

  function dragStart(event: DragEvent, calendarEvent: CalendarEvent) {
    if (!dragEnabled || calendarEvent.kind === 'milestone' || resizingRef.current) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.setData('text/plain', calendarEvent.source_id);
    event.dataTransfer.effectAllowed = 'move';
  }

  function allowDrop(event: DragEvent) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }

  /** Column-level drop: derive hour+minute from pointer Y so event blocks can't swallow the drop. */
  function dropOnColumn(event: DragEvent, date: string) {
    event.preventDefault();
    setPreview(null);
    const sourceId = event.dataTransfer.getData('text/plain');
    if (!sourceId) return;
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const totalMinutes = ((event.clientY - rect.top) / HOUR_HEIGHT) * 60;
    const clamped = Math.max(0, Math.min((WEEK_END_HOUR - WEEK_START_HOUR) * 60 - 15, totalMinutes));
    const snapped = snap15(clamped);
    onDropItem(sourceId, date, WEEK_START_HOUR + Math.floor(snapped / 60), snapped % 60);
  }

  /** Live target-time bubble while dragging over a column. */
  function dragOverColumn(event: DragEvent) {
    allowDrop(event);
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const totalMinutes = ((event.clientY - rect.top) / HOUR_HEIGHT) * 60;
    const clamped = Math.max(0, Math.min((WEEK_END_HOUR - WEEK_START_HOUR) * 60 - 15, totalMinutes));
    const snapped = snap15(clamped);
    const hour = WEEK_START_HOUR + Math.floor(snapped / 60);
    setPreview({ x: event.clientX + 14, y: event.clientY + 10, label: `${pad2(hour)}:${pad2(snapped % 60)}` });
  }

  function dropAllDay(event: DragEvent, date: string) {
    event.preventDefault();
    setPreview(null);
    const sourceId = event.dataTransfer.getData('text/plain');
    if (sourceId) onDropItem(sourceId, date, null, 0);
  }

  /** Bottom edge: adjust end (duration), start fixed. */
  function resizeEndStart(event: ReactPointerEvent, calendarEvent: CalendarEvent) {
    event.preventDefault();
    event.stopPropagation();
    resizingRef.current = true;
    const startY = event.clientY;
    const baseDuration = eventDurationMinutes(calendarEvent);
    const target = event.currentTarget as HTMLElement;
    target.setPointerCapture(event.pointerId);

    function onMove(move: PointerEvent) {
      const delta = snap15(((move.clientY - startY) / HOUR_HEIGHT) * 60);
      const next = Math.max(15, baseDuration + delta);
      setPreview({ x: move.clientX + 14, y: move.clientY + 10, label: `时长 ${Math.floor(next / 60)}:${pad2(next % 60)}` });
    }
    function onUp(up: PointerEvent) {
      const deltaMinutes = snap15(((up.clientY - startY) / HOUR_HEIGHT) * 60);
      resizingRef.current = false;
      setPreview(null);
      target.removeEventListener('pointermove', onMove);
      target.removeEventListener('pointerup', onUp);
      target.removeEventListener('pointercancel', onUp);
      if (deltaMinutes !== 0) onResizeItem(calendarEvent.source_id, baseDuration + deltaMinutes);
    }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
    target.addEventListener('pointercancel', onUp);
  }

  /** Top edge: adjust start, end fixed. */
  function resizeStartEdge(event: ReactPointerEvent, calendarEvent: CalendarEvent) {
    event.preventDefault();
    event.stopPropagation();
    resizingRef.current = true;
    const startY = event.clientY;
    const startParts = calendarEvent.start.includes('T') ? calendarEvent.start.slice(11, 16) : '00:00';
    const [sh, sm] = startParts.split(':').map(Number);
    const baseStartMinutes = sh * 60 + sm;
    const duration = eventDurationMinutes(calendarEvent);
    const target = event.currentTarget as HTMLElement;
    target.setPointerCapture(event.pointerId);

    function onMove(move: PointerEvent) {
      const delta = snap15(((move.clientY - startY) / HOUR_HEIGHT) * 60);
      const next = Math.max(0, Math.min(baseStartMinutes + duration - 15, baseStartMinutes + delta));
      setPreview({ x: move.clientX + 14, y: move.clientY + 10, label: `开始 ${pad2(Math.floor(next / 60))}:${pad2(next % 60)}` });
    }
    function onUp(up: PointerEvent) {
      const delta = snap15(((up.clientY - startY) / HOUR_HEIGHT) * 60);
      const next = Math.max(0, Math.min(baseStartMinutes + duration - 15, baseStartMinutes + delta));
      resizingRef.current = false;
      setPreview(null);
      target.removeEventListener('pointermove', onMove);
      target.removeEventListener('pointerup', onUp);
      target.removeEventListener('pointercancel', onUp);
      if (next !== baseStartMinutes) onResizeStartItem(calendarEvent.source_id, next);
    }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
    target.addEventListener('pointercancel', onUp);
  }

  return (
    <div className="week-grid">
      <div className="week-row week-head">
        <div className="week-gutter" />
        {dates.map((date, index) => (
          <div className={date === today ? 'week-day-head today' : 'week-day-head'} key={date}>
            <span>{WEEKDAY_LABELS[index]}</span>
            <strong>{date.slice(5)}</strong>
          </div>
        ))}
      </div>
      <div className="week-row week-allday">
        <div className="week-gutter">全天</div>
        {dates.map((date) => (
          <div className="week-allday-cell" key={date} onDragOver={allowDrop} onDrop={(event) => dropAllDay(event, date)}>
            {(buckets.get(date)?.allDay ?? []).map((event) => (
              <button
                className={`week-allday-chip ${event.kind} status-${event.status}${event.status !== 'done' && (event.end ? event.end.slice(0, 10) : event.start.slice(0, 10)) < today ? ' is-overdue' : ''}`}
                type="button"
                key={event.id}
                style={{ borderColor: event.color }}
                draggable={dragEnabled && event.kind !== 'milestone' && event.status !== 'done'}
                onDragStart={(dragEvent) => dragStart(dragEvent, event)}
                onClick={() => event.kind !== 'milestone' && onOpenItem(event.source_id)}
                title={event.kind === 'milestone' ? `里程碑：${event.title}` : event.title}
              >
                {event.kind === 'milestone' ? '◆ ' : ''}
                {event.title}
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="week-row week-body">
        <div className="week-gutter">
          {HOURS.map((hour) => (
            <div className="week-hour-label" style={{ height: HOUR_HEIGHT }} key={hour}>
              {hour}:00
            </div>
          ))}
        </div>
        {dates.map((date) => (
          <div
            className={date === today ? 'week-day-col today' : 'week-day-col'}
            key={date}
            onDragOver={dragOverColumn}
            onDragLeave={() => setPreview(null)}
            onDrop={(event) => dropOnColumn(event, date)}
          >
            {HOURS.map((hour) => (
              <div className="week-hour-row" style={{ height: HOUR_HEIGHT }} key={hour} />
            ))}
            {(buckets.get(date)?.timed ?? []).map((layout) => {
              const overdue = layout.event.status !== 'done' && date < today;
              const interactive = dragEnabled && layout.event.kind !== 'milestone' && layout.event.status !== 'done';
              return (
                <button
                  className={`week-event ${layout.event.kind} status-${layout.event.status}${overdue ? ' is-overdue' : ''}`}
                  type="button"
                  key={layout.event.id}
                  style={{ top: layout.top, height: layout.height, borderColor: layout.event.color }}
                  draggable={dragEnabled && layout.event.kind !== 'milestone' && layout.event.status !== 'done'}
                  onDragStart={(dragEvent) => dragStart(dragEvent, layout.event)}
                  onDragEnd={() => setPreview(null)}
                  onClick={() => layout.event.kind !== 'milestone' && onOpenItem(layout.event.source_id)}
                  title={layout.event.title}
                >
                  {interactive && (
                    <span
                      className="week-event-resize top"
                      title="拖动调整开始时间（15 分钟对齐）"
                      onPointerDown={(pointerEvent) => resizeStartEdge(pointerEvent, layout.event)}
                      onClick={(clickEvent) => clickEvent.stopPropagation()}
                    />
                  )}
                  <small>{formatScheduleTime(layout.event.start)}</small>
                  <span>{layout.event.status === 'done' ? `✓ ${layout.event.title}` : overdue ? `⚠ ${layout.event.title}` : layout.event.title}</span>
                  {interactive && (
                    <span
                      className="week-event-resize"
                      title="拖动调整结束时间（15 分钟对齐）"
                      onPointerDown={(pointerEvent) => resizeEndStart(pointerEvent, layout.event)}
                      onClick={(clickEvent) => clickEvent.stopPropagation()}
                    />
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
      {preview && (
        <div className="drag-preview" style={{ left: preview.x, top: preview.y }}>
          {preview.label}
        </div>
      )}
    </div>
  );
}
