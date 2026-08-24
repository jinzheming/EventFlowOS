import { Check } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Item } from '../api/client';
import { rowSegments, rowTooltip } from '../lib/itemRow';

export { rowSegments, rowTooltip };
import { personalScheduleLabel } from '../lib/dates';
import { isHighPriority } from '../lib/itemFilters';
import { formatDuration, priorityLabels } from '../lib/labels';
import { recurrenceBadge } from '../lib/recurrence';

/** 时间槽位：语义分级（今天/逾期/明天/未来/未安排/已完成）。 */
export function RowTimeSlot({ item }: { item: Item }) {
  const schedule = personalScheduleLabel(item);
  return <span className={`row-timeslot tone-${schedule.tone}`}>{schedule.label}</span>;
}

/** 优先级标记：仅高/紧急渲染。 */
export function RowPriorityMark({ item }: { item: Item }) {
  if (!isHighPriority(item)) return null;
  return <span className={`row-priority ${item.priority}`}>{priorityLabels[item.priority]}</span>;
}

/** 等待态标记（唯一保留的状态渲染）。 */
export function RowWaitingMark({ item }: { item: Item }) {
  if (item.status !== 'waiting') return null;
  const waitingPerson = (item.people ?? []).find((person) => person.role === 'waiting');
  return <span className="row-waiting">等待{waitingPerson ? ` · ${waitingPerson.name}` : ''}</span>;
}

export function RowSegments({ item }: { item: Item }) {
  const segments = rowSegments(item);
  if (segments.length === 0) return null;
  return (
    <>
      {segments.map((segment, index) => (
        <span className={`row-segment ${segment.kind}`} key={`${segment.kind}-${index}`}>
          {segment.color && <span className="tag-dot" style={{ background: segment.color }} />}
          {segment.label}
        </span>
      ))}
    </>
  );
}

export function ItemRowShell({
  className,
  selected,
  focused,
  done,
  tooltip,
  onOpen,
  check,
  selectCheck,
  leading,
  flow,
  timeslot,
  ops,
}: {
  className?: string;
  selected?: boolean;
  focused?: boolean;
  done?: boolean;
  tooltip?: string;
  onOpen: () => void;
  /** 完成圈；不传则不渲染（如已完成/归档视图由调用方决定） */
  check?: { done: boolean; onToggle: () => void };
  selectCheck?: { checked: boolean; onCheck: () => void };
  leading?: ReactNode;
  flow: ReactNode;
  timeslot?: ReactNode;
  ops?: ReactNode;
}) {
  const classes = ['item-row', className, selected ? 'active' : '', focused ? 'focused' : '', done ? 'done' : '']
    .filter(Boolean)
    .join(' ');
  return (
    <article
      className={classes}
      role="button"
      tabIndex={0}
      title={tooltip}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {selectCheck && (
        <input
          type="checkbox"
          className="batch-check"
          checked={selectCheck.checked}
          onChange={selectCheck.onCheck}
          onClick={(event) => event.stopPropagation()}
          aria-label="选择该事项"
        />
      )}
      {check && (
        <button
          className={check.done ? 'check done' : 'check'}
          title={check.done ? '重新打开' : '标记完成'}
          onClick={(event) => {
            event.stopPropagation();
            check.onToggle();
          }}
        >
          <Check size={14} />
        </button>
      )}
      {leading}
      <div className="row-flow">{flow}</div>
      {timeslot}
      {ops && <div className="row-ops">{ops}</div>}
    </article>
  );
}
