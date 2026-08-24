import type { Item, ItemPayload, ItemStatus, PersonRole, Priority, Scope } from '../api/client';
import { localDateTimeParts, localInputToISO } from './dates';
import type { RecurrenceEnd, RecurrenceFreq } from './recurrence';
import { buildRecurrenceRule, emptyRecurrenceFields, recurrenceFieldsFromItem } from './recurrence';

export type DraftPerson = {
  person_id: string;
  role: PersonRole;
};

export type WorkDraft = {
  title: string;
  project_id: string;
  priority: Priority;
  status: ItemStatus;
  start_date: string;
  start_time: string;
  due_date: string;
  due_time: string;
  waiting_on: string;
  people: DraftPerson[];
  waiting_follow_up: string;
  recurrence_freq: RecurrenceFreq;
  recurrence_interval: string;
  recurrence_end: RecurrenceEnd;
  recurrence_until: string;
  recurrence_count: string;
  estimated_minutes: string;
  notes: string;
  reminder_enabled: boolean;
  reminder_offset: number;
  reminder_external: boolean;
};

export type PersonalDraft = {
  title: string;
  start_date: string;
  start_time: string;
  due_date: string;
  due_time: string;
  waiting_on: string;
  people: DraftPerson[];
  recurrence_freq: RecurrenceFreq;
  recurrence_interval: string;
  recurrence_end: RecurrenceEnd;
  recurrence_until: string;
  recurrence_count: string;
  estimated_minutes: string;
  notes: string;
  reminder_enabled: boolean;
  reminder_offset: number;
  reminder_external: boolean;
};

export function emptyWorkDraft(): WorkDraft {
  return {
    title: '',
    project_id: '',
    priority: 'normal',
    status: 'planned',
    start_date: '',
    start_time: '',
    due_date: '',
    due_time: '',
    waiting_on: '',
    people: [],
    waiting_follow_up: '',
    ...emptyRecurrenceFields(),
    estimated_minutes: '',
    notes: '',
    reminder_enabled: false,
    reminder_offset: 0,
    reminder_external: false,
  };
}

export function emptyPersonalDraft(): PersonalDraft {
  return {
    title: '',
    start_date: '',
    start_time: '',
    due_date: '',
    due_time: '',
    waiting_on: '',
    people: [],
    ...emptyRecurrenceFields(),
    estimated_minutes: '',
    notes: '',
    reminder_enabled: false,
    reminder_offset: 0,
    reminder_external: false,
  };
}

export function draftFromItem(item: Item): WorkDraft {
  const dueParts = item.due_at ? localDateTimeParts(item.due_at) : null;
  const startParts = item.start_at ? localDateTimeParts(item.start_at) : null;
  return {
    title: item.title,
    project_id: item.project_id ?? '',
    priority: item.priority,
    status: item.status === 'inbox' ? 'planned' : item.status,
    start_date: startParts?.date ?? item.start_date ?? '',
    start_time: startParts?.time ?? '',
    due_date: dueParts?.date ?? item.due_date ?? '',
    due_time: dueParts?.time ?? '',
    waiting_on: item.waiting_on ?? '',
    people: (item.people ?? []).map((person) => ({ person_id: person.id, role: person.role })),
    waiting_follow_up: item.waiting_follow_up_date ?? '',
    ...recurrenceFieldsFromItem(item),
    estimated_minutes: item.estimated_minutes ? String(item.estimated_minutes) : '',
    notes: item.notes ?? '',
    reminder_enabled: false,
    reminder_offset: 0,
    reminder_external: false,
  };
}

export function personalDraftFromItem(item: Item): PersonalDraft {
  const dueParts = item.due_at ? localDateTimeParts(item.due_at) : null;
  const startParts = item.start_at ? localDateTimeParts(item.start_at) : null;
  return {
    title: item.title,
    start_date: startParts?.date ?? item.start_date ?? '',
    start_time: startParts?.time ?? '',
    due_date: dueParts?.date ?? item.due_date ?? '',
    due_time: dueParts?.time ?? '',
    waiting_on: item.waiting_on ?? '',
    people: (item.people ?? []).map((person) => ({ person_id: person.id, role: person.role })),
    ...recurrenceFieldsFromItem(item),
    estimated_minutes: item.estimated_minutes ? String(item.estimated_minutes) : '',
    notes: item.notes ?? '',
    reminder_enabled: false,
    reminder_offset: 0,
    reminder_external: false,
  };
}

export function hasDraftSchedule(draft: WorkDraft) {
  return Boolean(draft.due_date || draft.start_date);
}

export function hasPersonalDraftSchedule(draft: PersonalDraft) {
  return Boolean(draft.start_date || draft.due_date);
}

export function buildWorkPayload(draft: WorkDraft): ItemPayload & { title: string; scope: Scope } {
  return {
    ...buildWorkPatch(draft),
    title: draft.title.trim(),
    scope: 'work',
  };
}

export function buildWorkPatch(draft: WorkDraft): ItemPayload {
  const schedule = buildSchedule(draft);
  const waiting = draft.people.some((person) => person.role === 'waiting') || draft.status === 'waiting';
  return {
    title: draft.title.trim(),
    status: draft.status,
    priority: draft.priority,
    project_id: draft.project_id || null,
    notes: draft.notes.trim() || null,
    waiting_on: null,
    people: draft.people,
    waiting_follow_up_date: waiting ? draft.waiting_follow_up || null : null,
    ...buildRecurrenceRule(draft),
    estimated_minutes: draft.estimated_minutes ? Number(draft.estimated_minutes) : null,
    ...schedule,
  };
}

// Client-side mirror of the backend ck_item_schedule_order rule. Returns an
// error message when start is after due, otherwise null.
export function scheduleOrderError(draft: WorkDraft): string | null {
  const timed = Boolean(draft.due_time || draft.start_time);
  if (timed) {
    if (draft.start_date && draft.due_date) {
      const start = `${draft.start_date}T${draft.start_time || '00:00'}`;
      const due = `${draft.due_date}T${draft.due_time || '23:59'}`;
      if (start > due) return '开始时间不能晚于截止时间';
    }
    return null;
  }
  if (draft.start_date && draft.due_date && draft.start_date > draft.due_date) {
    return '开始日期不能晚于截止日期';
  }
  return null;
}

export function buildSchedule(draft: Pick<WorkDraft, 'start_date' | 'start_time' | 'due_date' | 'due_time'>): Pick<Item, 'all_day' | 'start_at' | 'due_at' | 'start_date' | 'due_date'> {
  const timed = Boolean(draft.due_time || draft.start_time);
  if (timed) {
    return {
      all_day: false,
      start_at: draft.start_date ? localInputToISO(draft.start_date, draft.start_time || '00:00') : null,
      due_at: draft.due_date ? localInputToISO(draft.due_date, draft.due_time || '23:59') : null,
      start_date: null,
      due_date: null,
    };
  }
  return {
    all_day: true,
    start_at: null,
    due_at: null,
    start_date: draft.start_date || null,
    due_date: draft.due_date || null,
  };
}

export function buildPersonalPayload(draft: PersonalDraft): ItemPayload & { title: string; scope: Scope } {
  return {
    ...buildPersonalPatch(draft),
    title: draft.title.trim(),
    scope: 'personal',
    status: 'planned',
    priority: 'normal',
    project_id: null,
  };
}

export function buildPersonalPatch(draft: PersonalDraft): ItemPayload {
  return {
    title: draft.title.trim(),
    notes: draft.notes.trim() || null,
    waiting_on: null,
    people: draft.people,
    ...buildRecurrenceRule(draft),
    estimated_minutes: draft.estimated_minutes ? Number(draft.estimated_minutes) : null,
    ...buildSchedule(draft),
  };
}

export function buildPersonalSchedule(draft: PersonalDraft): Pick<Item, 'all_day' | 'start_at' | 'due_at' | 'start_date' | 'due_date'> {
  return buildSchedule(draft);
}
