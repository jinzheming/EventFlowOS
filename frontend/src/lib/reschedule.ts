import type { Item } from '../api/client';
import { addDaysString, localInputToISO, todayString } from './dates';

// WP D: one-click reschedule. Every option sets all four schedule keys so the
// merged payload always satisfies the backend all_day/timed exclusivity rule.
export type RescheduleOption = 'tomorrow' | 'next_week' | 'tonight' | 'clear';

export const rescheduleOptions: { value: RescheduleOption; label: string }[] = [
  { value: 'tomorrow', label: '改到明天' },
  { value: 'next_week', label: '改到下周' },
  { value: 'tonight', label: '今晚 18:00' },
  { value: 'clear', label: '清除时间' },
];

export function buildReschedulePatch(option: RescheduleOption): Partial<Item> {
  if (option === 'tomorrow') {
    return { all_day: true, start_at: null, due_at: null, due_date: null, start_date: addDaysString(1) };
  }
  if (option === 'next_week') {
    return { all_day: true, start_at: null, due_at: null, due_date: null, start_date: addDaysString(7) };
  }
  if (option === 'tonight') {
    return { all_day: false, due_at: null, start_date: null, due_date: null, start_at: localInputToISO(todayString(), '18:00') };
  }
  return { all_day: true, start_at: null, due_at: null, start_date: null, due_date: null };
}
