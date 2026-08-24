import type { Item } from '../api/client';
import { addDaysString, itemDateKey, todayString } from './dates';

export type ItemQuickFilter = 'all' | 'today' | 'week' | 'overdue' | 'waiting' | 'unscheduled' | 'date_only';

export const workQuickFilters: ItemQuickFilter[] = ['all', 'today', 'week', 'overdue', 'waiting', 'unscheduled'];
export const personalQuickFilters: ItemQuickFilter[] = ['all', 'today', 'week', 'overdue', 'unscheduled'];
export const todayQuickFilters: ItemQuickFilter[] = ['all', 'overdue'];
export const calendarQuickFilters: ItemQuickFilter[] = ['all', 'today', 'overdue', 'date_only'];

export const quickFilterLabels: Record<ItemQuickFilter, string> = {
  all: '全部',
  today: '仅今日',
  week: '本周到期',
  overdue: '仅逾期',
  waiting: '仅等待',
  unscheduled: '仅无时间',
  date_only: '仅有日期',
};

export function matchesQuickFilter(item: Item, filter: ItemQuickFilter): boolean {
  if (filter === 'all') return true;
  const date = itemDateKey(item);
  const today = todayString();
  if (filter === 'today') return date === today;
  if (filter === 'week') {
    if (date === null) return false;
    const sunday = weekEndString();
    return date >= today && date <= sunday;
  }
  if (filter === 'overdue') return date !== null && date < today && item.status !== 'waiting' && item.status !== 'inbox';
  if (filter === 'waiting') return item.status === 'waiting';
  if (filter === 'unscheduled') return date === null;
  if (filter === 'date_only') return date !== null && !item.start_at && !item.due_at;
  return true;
}

export function filterItemsByQuickFilter(items: Item[], filter: ItemQuickFilter) {
  return items.filter((item) => matchesQuickFilter(item, filter));
}

/** Monday-based week end (Sunday) in session-local date terms. */
export function weekEndString(): string {
  const today = todayString();
  const [year, month, day] = today.split('-').map(Number);
  const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return addDaysString((7 - dow) % 7);
}

/** High-priority = high or urgent. */
export function isHighPriority(item: Item): boolean {
  return item.priority === 'high' || item.priority === 'urgent';
}
