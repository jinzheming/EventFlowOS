import { CalendarEvent } from '../api/client';
import { todayString } from '../lib/dates';
import { WEEKDAY_LABELS } from '../lib/week';

export function MonthGrid({
  dates,
  buckets,
  monthAnchor,
  onOpenItem,
  onJumpToDate,
}: {
  dates: string[];
  buckets: Map<string, CalendarEvent[]>;
  /** YYYY-MM-01 of the displayed month, for dimming out-of-month cells. */
  monthAnchor: string;
  onOpenItem: (sourceId: string) => void;
  onJumpToDate: (date: string) => void;
}) {
  const today = todayString();
  const monthPrefix = monthAnchor.slice(0, 7);

  return (
    <div className="month-grid">
      <div className="month-row month-head">
        {WEEKDAY_LABELS.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
      {Array.from({ length: 6 }, (_, week) => (
        <div className="month-row" key={week}>
          {dates.slice(week * 7, week * 7 + 7).map((date) => {
            const events = buckets.get(date) ?? [];
            const shown = events.slice(0, 3);
            const inMonth = date.startsWith(monthPrefix);
            return (
              <div
                className={`month-cell${date === today ? ' today' : ''}${inMonth ? '' : ' out-of-month'}`}
                key={date}
                role="button"
                tabIndex={0}
                title={`${date} · 点击跳转周视图`}
                onClick={() => onJumpToDate(date)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') onJumpToDate(date);
                }}
              >
                <span className="month-day-number">{Number(date.slice(8))}</span>
                {shown.map((event) => (
                  <button
                    className={`month-chip ${event.kind} status-${event.status}${event.status !== 'done' && (event.all_day ? (event.end ? event.end.slice(0, 10) : event.start.slice(0, 10)) : event.start.slice(0, 10)) < today ? ' is-overdue' : ''}`}
                    type="button"
                    key={event.id}
                    style={{ borderColor: event.color }}
                    title={event.title}
                    onClick={(clickEvent) => {
                      clickEvent.stopPropagation();
                      if (event.kind !== 'milestone') onOpenItem(event.source_id);
                    }}
                  >
                    {event.kind === 'milestone' ? '◆ ' : event.status === 'done' ? '✓ ' : (event.all_day ? (event.end ? event.end.slice(0, 10) : event.start.slice(0, 10)) : event.start.slice(0, 10)) < today ? '⚠ ' : ''}
                    {event.title}
                  </button>
                ))}
                {events.length > 3 && <span className="month-more">+{events.length - 3}</span>}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
