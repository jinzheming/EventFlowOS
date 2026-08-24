import type { PersonalDraft, WorkDraft } from './drafts';
import { addDaysString, formatScheduleTime, localInputToISO, todayString } from './dates';

const ALL_DAY_HOUR = '09:00';

export type ReminderPreview = {
  at: Date | null;
  label: string;
};

function subtractMinutes(iso: string, minutes: number) {
  return new Date(new Date(iso).getTime() - minutes * 60_000);
}

function formatPreviewLabel(at: Date) {
  return `将在 ${formatScheduleTime(at.toISOString())} 提醒`;
}

function previewFromParts(date: string, time: string, offsetMinutes: number): ReminderPreview {
  const at = subtractMinutes(localInputToISO(date, time), offsetMinutes);
  return { at, label: formatPreviewLabel(at) };
}

export function previewWorkReminder(draft: WorkDraft): ReminderPreview | null {
  if (!draft.reminder_enabled) return null;
  if (draft.start_date && draft.start_time) return previewFromParts(draft.start_date, draft.start_time, draft.reminder_offset);
  if (draft.start_date) return previewFromParts(draft.start_date, ALL_DAY_HOUR, draft.reminder_offset);
  if (draft.due_date && draft.due_time) return previewFromParts(draft.due_date, draft.due_time, draft.reminder_offset);
  if (draft.due_date) return previewFromParts(draft.due_date, ALL_DAY_HOUR, draft.reminder_offset);
  return { at: null, label: '先设置开始日期或截止日期' };
}

export function previewPersonalReminder(draft: PersonalDraft): ReminderPreview | null {
  if (!draft.reminder_enabled) return null;
  if (draft.start_date && draft.start_time) return previewFromParts(draft.start_date, draft.start_time, draft.reminder_offset);
  if (draft.start_date) return previewFromParts(draft.start_date, ALL_DAY_HOUR, draft.reminder_offset);
  if (draft.due_date && draft.due_time) return previewFromParts(draft.due_date, draft.due_time, draft.reminder_offset);
  if (draft.due_date) return previewFromParts(draft.due_date, ALL_DAY_HOUR, draft.reminder_offset);
  return { at: null, label: '先设置开始日期或时间' };
}

export function snoozeWakeAt(kind: '10m' | '1h' | 'tomorrow9'): string {
  if (kind === '10m') return new Date(Date.now() + 10 * 60_000).toISOString();
  if (kind === '1h') return new Date(Date.now() + 60 * 60_000).toISOString();
  return localInputToISO(addDaysString(1), ALL_DAY_HOUR);
}

export function snoozeLabel(kind: '10m' | '1h' | 'tomorrow9') {
  if (kind === '10m') return '10 分钟后';
  if (kind === '1h') return '1 小时后';
  return '明天 9:00';
}

export function formatSnoozeWake(iso: string) {
  const date = iso.slice(0, 10);
  if (date === todayString()) return `稍后 ${formatScheduleTime(iso)}`;
  return `延后到 ${formatScheduleTime(iso)}`;
}
