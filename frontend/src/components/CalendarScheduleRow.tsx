import { formatScheduleTime } from '../lib/dates';
import { scopeLabel, statusLabels } from '../lib/labels';
import { TimedSchedule } from '../lib/calendar';

export function CalendarScheduleRow({ schedule, onOpen }: { schedule: TimedSchedule; onOpen: () => void }) {
  const item = schedule.item;
  return (
    <article
      className={`calendar-row ${item.scope} status-${item.status}`}
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      <time className="calendar-time">{formatScheduleTime(schedule.time)}</time>
      <div className="calendar-row-main">
        <strong>{item.title}</strong>
        <div className="calendar-tags">
          <span>{scopeLabel(item.scope)}</span>
          <span>{schedule.relation}</span>
          {item.scope === 'work' && <span>项目：{item.project_name ?? '未关联'}</span>}
          <span>{statusLabels[item.status]}</span>
        </div>
      </div>
    </article>
  );
}
