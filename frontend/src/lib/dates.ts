import type { Item } from '../api/client';

// WP D: session.timezone-aware date handling. When the backend session reports a
// timezone (e.g. Asia/Shanghai), all "today / tomorrow / local parts" logic uses
// that zone instead of the browser's zone. Null means "browser local" (legacy).
let appTimezone: string | null = null;

export function setAppTimezone(timezone: string | null) {
  appTimezone = timezone && timezone.trim() ? timezone : null;
}

export function getAppTimezone() {
  return appTimezone;
}

function partsInTimezone(value: Date, timezone: string) {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
  const parts: Record<string, string> = {};
  for (const part of formatter.formatToParts(value)) {
    if (part.type !== 'literal') parts[part.type] = part.value;
  }
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${parts.hour === '24' ? '00' : parts.hour}:${parts.minute}`,
  };
}

export function localDateTimeParts(value: string) {
  const date = new Date(value);
  if (appTimezone) return partsInTimezone(date, appTimezone);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return { date: `${year}-${month}-${day}`, time: `${hour}:${minute}` };
}

export function todayString() {
  return addDaysString(0);
}

export function addDaysString(days: number) {
  const base = appTimezone ? partsInTimezone(new Date(), appTimezone).date : null;
  let date: Date;
  if (base) {
    const [year, month, day] = base.split('-').map(Number);
    date = new Date(Date.UTC(year, month - 1, day + days));
    const y = date.getUTCFullYear();
    const m = String(date.getUTCMonth() + 1).padStart(2, '0');
    const d = String(date.getUTCDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  date = new Date();
  date.setDate(date.getDate() + days);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Convert a wall-clock date+time in the app timezone to an ISO instant.
export function localInputToISO(date: string, time: string): string {
  const hhmm = time || '00:00';
  if (!appTimezone) return new Date(`${date}T${hhmm}:00`).toISOString();
  // Iteratively solve: find the UTC instant whose parts in appTimezone equal the input.
  let guess = new Date(`${date}T${hhmm}:00Z`);
  for (let i = 0; i < 2; i += 1) {
    const parts = partsInTimezone(guess, appTimezone);
    const rendered = new Date(`${parts.date}T${parts.time}:00Z`);
    const desired = new Date(`${date}T${hhmm}:00Z`);
    guess = new Date(guess.getTime() + (desired.getTime() - rendered.getTime()));
  }
  return guess.toISOString();
}

function tzOptions(): { timeZone?: string } {
  return appTimezone ? { timeZone: appTimezone } : {};
}

export function formatUpdatedAt(value: string) {
  return new Date(value).toLocaleString([], { ...tzOptions(), month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function formatScheduleTime(value: string) {
  const parts = localDateTimeParts(value);
  const time = new Date(value).toLocaleTimeString([], { ...tzOptions(), hour: '2-digit', minute: '2-digit' });
  if (parts.date === todayString()) return time;
  return `${parts.date.slice(5)} ${time}`;
}

export function itemStartKey(item: Item) {
  if (item.start_date) return item.start_date;
  if (item.start_at) return localDateTimeParts(item.start_at).date;
  return null;
}

export function itemDueKey(item: Item) {
  if (item.due_date) return item.due_date;
  if (item.due_at) return localDateTimeParts(item.due_at).date;
  return null;
}

export function itemDateKey(item: Item) {
  return itemStartKey(item) ?? itemDueKey(item);
}

function formatDateSpan(start: string | null, end: string | null, fallback: string) {
  if (start && end && start !== end) return `${start.slice(5)} → ${end.slice(5)}`;
  return end ?? start ?? fallback;
}

export function formatItemSchedule(item: Item) {
  if (item.all_day) {
    return formatDateSpan(item.start_date, item.due_date, '未安排');
  }
  const formatInstant = (value: string) =>
    new Date(value).toLocaleString([], { ...tzOptions(), month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  if (item.start_at && item.due_at) return `${formatInstant(item.start_at)} → ${formatInstant(item.due_at)}`;
  if (item.due_at) return formatInstant(item.due_at);
  if (item.start_at) return formatInstant(item.start_at);
  return '未安排';
}

export function scheduleBadge(item: Item) {
  const date = itemDateKey(item);
  if (!date) return { label: '时间：未安排', tone: 'muted' };
  const today = todayString();
  if (date < today) return { label: `逾期：${formatItemSchedule(item)}`, tone: 'danger' };
  if (date === today) return { label: `今天：${formatItemSchedule(item)}`, tone: 'today' };
  if (date === addDaysString(1)) return { label: `明天：${formatItemSchedule(item)}`, tone: 'soon' };
  return { label: `计划：${formatItemSchedule(item)}`, tone: 'muted' };
}

export function personalScheduleLabel(item: Item) {
  const date = itemDateKey(item);
  if (item.status === 'done' && item.completed_at) return { label: `已完成 ${formatUpdatedAt(item.completed_at)}`, tone: 'done' };
  if (!date) return { label: '未安排', tone: 'muted' };
  const today = todayString();
  if (date < today) return { label: `逾期 ${formatItemSchedule(item)}`, tone: 'danger' };
  if (date === today) return { label: `今天 ${formatItemSchedule(item)}`, tone: 'today' };
  if (date === addDaysString(1)) return { label: `明天 ${formatItemSchedule(item)}`, tone: 'soon' };
  return { label: formatItemSchedule(item), tone: 'muted' };
}

export function isDueTodayOrEarlier(item: Item) {
  const date = itemDueKey(item) ?? itemStartKey(item);
  return date !== null && date <= todayString();
}

export function isWaitingItem(item: Item) {
  return item.status === 'waiting' || (item.people ?? []).some((person) => person.role === 'waiting');
}

export function isMustDoToday(item: Item) {
  if (item.archived_at || item.status === 'done' || item.status === 'cancelled' || isWaitingItem(item)) return false;
  const due = itemDueKey(item);
  if (due) return due <= todayString();
  const start = itemStartKey(item);
  return start !== null && start <= todayString();
}

export function hasConcreteStartToday(item: Item) {
  if (item.archived_at || item.status === 'done' || item.status === 'cancelled') return false;
  if (item.start_at) return localDateTimeParts(item.start_at).date === todayString();
  return false;
}
