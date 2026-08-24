import type { Item, Project, Scope } from '../api/client';
import { addDaysString, localDateTimeParts, localInputToISO, todayString } from './dates';

export type CalendarScopeFilter = 'all' | Scope;

export type TimedSchedule = {
  item: Item;
  time: string;
  relation: '开始' | '截止';
};

export function timedSchedulesForItem(item: Item): TimedSchedule[] {
  if (item.status === 'done' || item.status === 'cancelled' || item.archived_at) return [];
  const schedules: TimedSchedule[] = [];
  if (item.start_at) schedules.push({ item, time: item.start_at, relation: '开始' });
  if (item.due_at) schedules.push({ item, time: item.due_at, relation: '截止' });
  return schedules;
}

export function compareTimedSchedules(a: TimedSchedule, b: TimedSchedule) {
  return new Date(a.time).getTime() - new Date(b.time).getTime();
}

export function groupTimedSchedules(schedules: TimedSchedule[]) {
  const today = todayString();
  const weekEnd = addDaysString(7);
  return [
    { label: '已过时间', schedules: schedules.filter((schedule) => localDateTimeParts(schedule.time).date < today) },
    { label: '今天', schedules: schedules.filter((schedule) => localDateTimeParts(schedule.time).date === today) },
    {
      label: '未来 7 天',
      schedules: schedules.filter((schedule) => {
        const date = localDateTimeParts(schedule.time).date;
        return date > today && date <= weekEnd;
      }),
    },
    { label: '以后', schedules: schedules.filter((schedule) => localDateTimeParts(schedule.time).date > weekEnd) },
  ];
}

export function hasDateOnlySchedule(item: Item) {
  if (item.status === 'done' || item.status === 'cancelled' || item.archived_at) return false;
  return !item.start_at && !item.due_at && Boolean(item.start_date || item.due_date);
}

export function compareDateOnlyItems(a: Item, b: Item) {
  return dateOnlyKey(a).localeCompare(dateOnlyKey(b));
}

export function dateOnlyKey(item: Item) {
  return item.start_date ?? item.due_date ?? '9999-12-31';
}

export function dateOnlyLabel(item: Item) {
  return item.start_date ? `开始 ${item.start_date}` : `截止 ${item.due_date}`;
}

export function dateOnlyTimeOptions(scope: Scope) {
  if (scope === 'work') {
    return [
      { label: '上午', time: '09:00' },
      { label: '下午', time: '14:00' },
      { label: '傍晚', time: '18:00' },
    ];
  }
  return [
    { label: '上午', time: '09:00' },
    { label: '下午', time: '15:00' },
    { label: '晚上', time: '20:00' },
  ];
}

export function buildDateOnlyTimePatch(item: Item, time: string): Partial<Item> {
  const date = item.start_date ?? item.due_date;
  if (!date) return {};
  // Always clear both date fields and set only datetime fields, so the merged
  // payload satisfies the backend timed/all-day exclusivity rule even for
  // items that span a start→due date range.
  const patch: Partial<Item> = { all_day: false, start_date: null, due_date: null, start_at: null, due_at: null };
  if (item.start_date && item.due_date) {
    patch.start_at = localInputToISO(item.start_date, item.start_date === date ? time : '00:00');
    patch.due_at = localInputToISO(item.due_date, item.due_date === date ? time : '23:59');
  } else if (item.start_date) {
    patch.start_at = localInputToISO(item.start_date, time);
  } else {
    patch.due_at = localInputToISO(item.due_date as string, time);
  }
  return patch;
}
