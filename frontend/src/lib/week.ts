import type { CalendarEvent, Item } from '../api/client';
import { addDaysString, localDateTimeParts, localInputToISO, todayString } from './dates';

// WP E: week-grid helpers. All date math goes through lib/dates so it follows
// the session timezone.
export const WEEK_START_HOUR = 7;
export const WEEK_END_HOUR = 21;
export const HOUR_HEIGHT = 44;

export const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

function pad(value: number) {
  return String(value).padStart(2, '0');
}

export function weekDates(offset: number): string[] {
  const [year, month, day] = todayString().split('-').map(Number);
  const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  const mondayDelta = -((dow + 6) % 7) + offset * 7;
  return Array.from({ length: 7 }, (_, index) => addDaysString(mondayDelta + index));
}

export function shiftDateString(date: string, deltaDays: number): string {
  const [year, month, day] = date.split('-').map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day + deltaDays));
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())}`;
}

function dayDiff(from: string, to: string): number {
  const [fy, fm, fd] = from.split('-').map(Number);
  const [ty, tm, td] = to.split('-').map(Number);
  return Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / 86400000);
}

export type WeekEventLayout = {
  event: CalendarEvent;
  top: number;
  height: number;
};

export type WeekDayBucket = {
  allDay: CalendarEvent[];
  timed: WeekEventLayout[];
};

export function splitEventsForWeek(events: CalendarEvent[], dates: string[]): Map<string, WeekDayBucket> {
  const byDate = new Map<string, WeekDayBucket>();
  for (const date of dates) byDate.set(date, { allDay: [], timed: [] });
  for (const event of events) {
    if (event.status === 'cancelled') continue;
    if (event.all_day) {
      const startDate = event.start.slice(0, 10);
      const endDate = event.end ? event.end.slice(0, 10) : startDate;
      for (const date of dates) {
        if (date >= startDate && date <= endDate) byDate.get(date)?.allDay.push(event);
      }
      continue;
    }
    const parts = localDateTimeParts(event.start);
    const bucket = byDate.get(parts.date);
    if (!bucket) continue;
    const [hour, minute] = parts.time.split(':').map(Number);
    const startMinutes = hour * 60 + minute;
    let durationMinutes = 60;
    if (event.end) {
      const endParts = localDateTimeParts(event.end);
      const [endHour, endMinute] = endParts.time.split(':').map(Number);
      const endMinutes = endParts.date === parts.date ? endHour * 60 + endMinute : WEEK_END_HOUR * 60;
      durationMinutes = Math.max(30, endMinutes - startMinutes);
    }
    const clampedStart = Math.min(Math.max(startMinutes, WEEK_START_HOUR * 60), WEEK_END_HOUR * 60 - 30);
    const heightMinutes = Math.min(durationMinutes, WEEK_END_HOUR * 60 - clampedStart);
    bucket.timed.push({
      event,
      top: ((clampedStart - WEEK_START_HOUR * 60) / 60) * HOUR_HEIGHT,
      height: Math.max(22, (heightMinutes / 60) * HOUR_HEIGHT),
    });
  }
  for (const bucket of byDate.values()) {
    bucket.timed.sort((a, b) => a.top - b.top);
    bucket.allDay.sort((a, b) => a.title.localeCompare(b.title, 'zh'));
  }
  return byDate;
}

// Drag an item onto a day (targetHour === null → all-day) or an hour lane.
// Always sets all four schedule keys so the merged payload stays valid.
export function snap15(minutes: number): number {
  return Math.max(0, Math.round(minutes / 15) * 15);
}

export function buildDragPatch(item: Item, targetDate: string, targetHour: number | null, targetMinute = 0): Partial<Item> {
  if (targetHour === null) {
    if (item.all_day) {
      const anchor = item.due_date ?? item.start_date;
      const delta = anchor ? dayDiff(anchor, targetDate) : 0;
      return {
        all_day: true,
        start_at: null,
        due_at: null,
        start_date: item.start_date ? shiftDateString(item.start_date, delta) : null,
        due_date: item.due_date ? shiftDateString(item.due_date, delta) : targetDate,
      };
    }
    return { all_day: true, start_at: null, due_at: null, start_date: null, due_date: targetDate };
  }
  const targetTime = `${pad(targetHour)}:${pad(targetMinute)}`;
  if (!item.all_day && (item.due_at || item.start_at)) {
    const anchorISO = (item.due_at ?? item.start_at) as string;
    const nextAnchor = localInputToISO(targetDate, targetTime);
    const deltaMs = new Date(nextAnchor).getTime() - new Date(anchorISO).getTime();
    // Keep the anchor semantics: shifting due moves start along, and vice versa.
    const shift = (value: string | null) => (value ? new Date(new Date(value).getTime() + deltaMs).toISOString() : null);
    return { all_day: false, start_date: null, due_date: null, start_at: shift(item.start_at), due_at: shift(item.due_at) };
  }
  return {
    all_day: false,
    start_date: null,
    due_date: null,
    start_at: null,
    due_at: localInputToISO(targetDate, targetTime),
  };
}

/** Duration of a timed calendar event in minutes (defaults to 60 when no end). */
export function eventDurationMinutes(event: CalendarEvent): number {
  if (!event.end) return 60;
  const startParts = localDateTimeParts(event.start);
  const endParts = localDateTimeParts(event.end);
  const [sh, sm] = startParts.time.split(':').map(Number);
  const [eh, em] = endParts.time.split(':').map(Number);
  const sameDay = startParts.date === endParts.date;
  return Math.max(15, (sameDay ? eh * 60 + em : 24 * 60) - (sh * 60 + sm));
}

/** Resize a timed item by setting due_at = start_at + durationMinutes (>=15). */
export function buildResizePatch(item: Item, durationMinutes: number): Partial<Item> {
  const startISO = item.start_at ?? item.due_at;
  if (!startISO || item.all_day) return {};
  const clamped = Math.max(15, snap15(durationMinutes));
  return { due_at: new Date(new Date(startISO).getTime() + clamped * 60000).toISOString() };
}

/** 42 Monday-first dates covering the month `offset` months from today. */
export function monthDates(offset: number): string[] {
  const [year, month] = todayString().split('-').map(Number);
  const first = new Date(Date.UTC(year, month - 1 + offset, 1));
  const dow = first.getUTCDay();
  const mondayDelta = -((dow + 6) % 7);
  const firstStr = `${first.getUTCFullYear()}-${pad(first.getUTCMonth() + 1)}-${pad(first.getUTCDate())}`;
  return Array.from({ length: 42 }, (_, index) => shiftDateString(firstStr, mondayDelta + index));
}

/** The week-grid offset whose Monday week contains `date`. */
export function weekOffsetForDate(date: string): number {
  const monday = weekDates(0)[0];
  return Math.floor(dayDiff(monday, date) / 7);
}

/** Bucket events per calendar date for the month grid (multi-day all-day expands). */
export function splitEventsForMonth(events: CalendarEvent[], dates: string[]): Map<string, CalendarEvent[]> {
  const byDate = new Map<string, CalendarEvent[]>();
  for (const date of dates) byDate.set(date, []);
  for (const event of events) {
    if (event.status === 'cancelled') continue;
    if (event.all_day) {
      const startDate = event.start.slice(0, 10);
      const endDate = event.end ? event.end.slice(0, 10) : startDate;
      for (const date of dates) {
        if (date >= startDate && date <= endDate) byDate.get(date)?.push(event);
      }
      continue;
    }
    const date = localDateTimeParts(event.start).date;
    byDate.get(date)?.push(event);
  }
  for (const bucket of byDate.values()) bucket.sort((a, b) => a.start.localeCompare(b.start));
  return byDate;
}

/** Resize from the top edge: move start_at to startMinutes (same day), keep due_at fixed. */
export function buildStartResizePatch(item: Item, startMinutes: number): Partial<Item> {
  if (!item.start_at || !item.due_at || item.all_day) return {};
  const date = item.start_at.slice(0, 10);
  const nextStart = localInputToISO(date, `${pad(Math.floor(startMinutes / 60))}:${pad(startMinutes % 60)}`);
  const minStart = new Date(item.due_at).getTime() - 15 * 60000;
  if (new Date(nextStart).getTime() > minStart) return {};
  return { start_at: nextStart };
}

/** Apply scope + quick filters to calendar events (week/month buckets). */
export function eventMatchesFilters(event: CalendarEvent, scope: string, quick: string): boolean {
  if (scope !== 'all') {
    const eventScope = event.kind === 'work_item' ? 'work' : event.kind === 'personal_item' ? 'personal' : null;
    if (eventScope !== scope) return false; // 里程碑在范围筛选下隐藏
  }
  const date = event.start.slice(0, 10);
  const endDate = event.end ? event.end.slice(0, 10) : date;
  const today = todayString();
  if (quick === 'today') return date <= today && endDate >= today;
  if (quick === 'overdue') return endDate < today && event.status !== 'done';
  if (quick === 'date_only') return event.all_day;
  return true;
}
