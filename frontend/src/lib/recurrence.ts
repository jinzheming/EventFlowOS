import type { Item } from '../api/client';

// WP F: recurrence presets for quick-add parsing; interval/until/count are
// editable in the item drawers (完成时自动生成下一次).
export type RecurrenceChoice = '' | 'daily' | 'weekly' | 'biweekly' | 'monthly';

export const recurrenceOptions: { value: RecurrenceChoice; label: string }[] = [
  { value: '', label: '不重复' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'biweekly', label: '每两周' },
  { value: 'monthly', label: '每月' },
];

export type RecurrenceFreq = '' | 'daily' | 'weekly' | 'monthly';
export type RecurrenceEnd = '' | 'until' | 'count';

export type RecurrenceDraftFields = {
  recurrence_freq: RecurrenceFreq;
  recurrence_interval: string;
  recurrence_end: RecurrenceEnd;
  recurrence_until: string;
  recurrence_count: string;
};

export const recurrenceFreqOptions: { value: RecurrenceFreq; label: string; unit: string }[] = [
  { value: '', label: '不重复', unit: '' },
  { value: 'daily', label: '每天', unit: '天' },
  { value: 'weekly', label: '每周', unit: '周' },
  { value: 'monthly', label: '每月', unit: '月' },
];

export function emptyRecurrenceFields(): RecurrenceDraftFields {
  return { recurrence_freq: '', recurrence_interval: '1', recurrence_end: '', recurrence_until: '', recurrence_count: '' };
}

export function choiceToRecurrenceFields(choice: RecurrenceChoice): RecurrenceDraftFields {
  const base = emptyRecurrenceFields();
  if (choice === 'daily') return { ...base, recurrence_freq: 'daily' };
  if (choice === 'weekly') return { ...base, recurrence_freq: 'weekly' };
  if (choice === 'biweekly') return { ...base, recurrence_freq: 'weekly', recurrence_interval: '2' };
  if (choice === 'monthly') return { ...base, recurrence_freq: 'monthly' };
  return base;
}

export function recurrenceFieldsFromItem(item: Item): RecurrenceDraftFields {
  if (!item.recurrence_freq) return emptyRecurrenceFields();
  return {
    recurrence_freq: item.recurrence_freq,
    recurrence_interval: String(item.recurrence_interval ?? 1),
    recurrence_end: item.recurrence_until ? 'until' : item.recurrence_count ? 'count' : '',
    recurrence_until: item.recurrence_until ?? '',
    recurrence_count: item.recurrence_count ? String(item.recurrence_count) : '',
  };
}

export function buildRecurrenceRule(
  fields: RecurrenceDraftFields,
): Pick<Item, 'recurrence_freq' | 'recurrence_interval' | 'recurrence_until' | 'recurrence_count'> {
  if (!fields.recurrence_freq) {
    return { recurrence_freq: null, recurrence_interval: null, recurrence_until: null, recurrence_count: null };
  }
  const interval = Math.max(1, Math.min(99, Number(fields.recurrence_interval) || 1));
  return {
    recurrence_freq: fields.recurrence_freq,
    recurrence_interval: interval,
    recurrence_until: fields.recurrence_end === 'until' && fields.recurrence_until ? fields.recurrence_until : null,
    recurrence_count:
      fields.recurrence_end === 'count' && fields.recurrence_count
        ? Math.max(1, Math.min(999, Number(fields.recurrence_count) || 1))
        : null,
  };
}

export function recurrenceBadge(item: Item): string | null {
  if (!item.recurrence_freq) return null;
  const interval = item.recurrence_interval ?? 1;
  const unit = item.recurrence_freq === 'daily' ? '天' : item.recurrence_freq === 'weekly' ? '周' : '月';
  const base = interval === 1 ? `↻ 每${unit}` : `↻ 每${interval}${unit}`;
  if (item.recurrence_until) return `${base} · 至 ${item.recurrence_until.slice(5)}`;
  if (item.recurrence_count) return `${base} · 共 ${item.recurrence_count} 次`;
  return base;
}
