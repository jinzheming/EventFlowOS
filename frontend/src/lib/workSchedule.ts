export type ScheduleDraft = {
  start_date: string;
  start_time: string;
  due_date: string;
  due_time: string;
  estimated_minutes: string;
};

function minutesFromTime(value: string) {
  const [hour, minute] = value.split(':').map(Number);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;
  return hour * 60 + minute;
}

function timeFromMinutes(value: number) {
  const day = 24 * 60;
  const normalized = ((Math.round(value) % day) + day) % day;
  const hour = String(Math.floor(normalized / 60)).padStart(2, '0');
  const minute = String(normalized % 60).padStart(2, '0');
  return `${hour}:${minute}`;
}

function addDays(date: string, days: number) {
  const [year, month, day] = date.split('-').map(Number);
  const value = new Date(Date.UTC(year, month - 1, day + days));
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, '0')}-${String(value.getUTCDate()).padStart(2, '0')}`;
}

export function deriveDueFromStart(startDate: string, startTime: string, estimatedMinutes: string) {
  const start = minutesFromTime(startTime);
  const duration = estimatedMinutes ? Number(estimatedMinutes) : null;
  if (!startDate || start === null || !duration || duration <= 0) return null;
  const dueTotal = start + duration;
  return {
    due_date: addDays(startDate, Math.floor(dueTotal / (24 * 60))),
    due_time: timeFromMinutes(dueTotal),
  };
}

export function deriveEstimatedFromRange(startDate: string, startTime: string, dueDate: string, dueTime: string) {
  const start = minutesFromTime(startTime);
  const due = minutesFromTime(dueTime);
  if (!startDate || !dueDate || start === null || due === null) return '';
  const startDateValue = Date.parse(`${startDate}T00:00:00Z`);
  const dueDateValue = Date.parse(`${dueDate}T00:00:00Z`);
  const dayDelta = Math.round((dueDateValue - startDateValue) / 86_400_000);
  const minutes = dayDelta * 24 * 60 + due - start;
  return minutes > 0 ? String(minutes) : '';
}

export function applyStartTime<T extends ScheduleDraft>(draft: T, startTime: string): T {
  const next = { ...draft, start_time: startTime };
  const due = deriveDueFromStart(next.start_date, next.start_time, next.estimated_minutes);
  return due ? { ...next, ...due } : next;
}

export function applyStartDate<T extends ScheduleDraft>(draft: T, startDate: string): T {
  const next = { ...draft, start_date: startDate };
  const due = deriveDueFromStart(next.start_date, next.start_time, next.estimated_minutes);
  return due ? { ...next, ...due } : next;
}

export function applyEstimatedMinutes<T extends ScheduleDraft>(draft: T, estimatedMinutes: string): T {
  const next = { ...draft, estimated_minutes: estimatedMinutes };
  const due = deriveDueFromStart(next.start_date, next.start_time, next.estimated_minutes);
  return due ? { ...next, ...due } : next;
}

export function applyDueTime<T extends ScheduleDraft>(draft: T, dueTime: string): T {
  const next = { ...draft, due_time: dueTime };
  const estimated = deriveEstimatedFromRange(next.start_date, next.start_time, next.due_date, next.due_time);
  return estimated ? { ...next, estimated_minutes: estimated } : next;
}

export function applyDueDate<T extends ScheduleDraft>(draft: T, dueDate: string): T {
  const next = { ...draft, due_date: dueDate };
  const estimated = deriveEstimatedFromRange(next.start_date, next.start_time, next.due_date, next.due_time);
  return estimated ? { ...next, estimated_minutes: estimated } : next;
}

export function normalizeCreateDraft<T extends ScheduleDraft>(draft: T): T {
  if (!draft.start_date && draft.due_date) {
    const next = { ...draft, start_date: draft.due_date, start_time: draft.due_time, due_date: '', due_time: '' };
    const due = deriveDueFromStart(next.start_date, next.start_time, next.estimated_minutes);
    return due ? { ...next, ...due } : next;
  }
  const due = deriveDueFromStart(draft.start_date, draft.start_time, draft.estimated_minutes);
  return due ? { ...draft, ...due } : draft;
}

export function normalizeWorkCreateDraft<T extends ScheduleDraft>(draft: T): T {
  return normalizeCreateDraft(draft);
}

export function reminderTiming(draft: ScheduleDraft): 'before_start' | 'before_due' {
  return draft.start_date || draft.start_time ? 'before_start' : 'before_due';
}

export function workReminderTiming(draft: ScheduleDraft): 'before_start' | 'before_due' {
  return reminderTiming(draft);
}
