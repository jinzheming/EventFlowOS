import type { Item, Project } from '../api/client';
import { addDaysString, formatItemSchedule, itemDateKey, localDateTimeParts, todayString } from './dates';
import { eventFormatLabels, ItemListView } from './labels';

export const HISTORY_BATCH_SIZE = 30;

type HistoryItemListView = Extract<ItemListView, 'done' | 'archived'>;

export interface ItemGroup {
  label: string;
  items: Item[];
}

export interface HistoryWindow {
  items: Item[];
  visibleCount: number;
  totalCount: number;
  hasMore: boolean;
}

export function groupWorkItems(items: Item[]): ItemGroup[] {
  const today = todayString();
  const active = items.filter((item) => item.status !== 'done' && item.status !== 'cancelled' && item.status !== 'inbox');
  const waiting = active.filter((item) => item.status === 'waiting');
  const actionable = active.filter((item) => item.status !== 'waiting');
  return [
    {
      label: '今天与逾期',
      items: actionable.filter((item) => {
        const date = itemDateKey(item);
        return date !== null && date <= today;
      }),
    },
    {
      label: '未来',
      items: actionable.filter((item) => {
        const date = itemDateKey(item);
        return date !== null && date > today;
      }),
    },
    {
      label: '无时间',
      items: actionable.filter((item) => itemDateKey(item) === null),
    },
    { label: '等待他人', items: waiting },
  ];
}

export function groupPersonalItems(items: Item[]): ItemGroup[] {
  const today = todayString();
  const active = items.filter((item) => item.status !== 'done' && item.status !== 'cancelled' && item.status !== 'inbox');
  return [
    {
      label: '今天与逾期',
      items: active.filter((item) => {
        const date = itemDateKey(item);
        return date !== null && date <= today;
      }),
    },
    {
      label: '未来',
      items: active.filter((item) => {
        const date = itemDateKey(item);
        return date !== null && date > today;
      }),
    },
    {
      label: '无时间',
      items: active.filter((item) => itemDateKey(item) === null),
    },
  ];
}

export function summarizeWorkItems(items: Item[]) {
  const groups = groupWorkItems(items);
  const today = todayString();
  const weekEnd = addDaysString(7);
  return {
    today: groups[0].items.length,
    upcoming: groups[1].items.filter((item) => {
      const date = itemDateKey(item);
      return date !== null && date > today && date <= weekEnd;
    }).length,
    unscheduled: groups[2].items.length,
    waiting: groups[3].items.length,
  };
}

export function filterItemsForView(items: Item[], view: ItemListView, query: string, projectById?: Map<string, Project>) {
  return items.filter((item) => {
    if (view === 'current' && (item.archived_at || item.status === 'done' || item.status === 'cancelled')) return false;
    if (view === 'done' && (item.archived_at || item.status !== 'done')) return false;
    if (view === 'archived' && !item.archived_at) return false;
    return matchesItemSearch(item, query, projectById);
  });
}

function historyTimestamp(item: Item, view: HistoryItemListView) {
  if (view === 'done') return item.completed_at ?? item.updated_at;
  if (item.status === 'done') return item.completed_at ?? item.archived_at ?? item.updated_at;
  return item.archived_at ?? item.updated_at;
}

function timestampValue(value: string | null) {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
}

export function sortHistoryItems(items: Item[], view: HistoryItemListView) {
  return [...items].sort((left, right) => {
    const timestampDiff = timestampValue(historyTimestamp(right, view)) - timestampValue(historyTimestamp(left, view));
    if (timestampDiff !== 0) return timestampDiff;
    const updatedDiff = timestampValue(right.updated_at) - timestampValue(left.updated_at);
    if (updatedDiff !== 0) return updatedDiff;
    return left.title.localeCompare(right.title, 'zh-Hans');
  });
}

function addDateDays(dateKey: string, days: number) {
  const [year, month, day] = dateKey.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function weekStartKey(dateKey: string) {
  const [year, month, day] = dateKey.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  const weekday = date.getUTCDay();
  const mondayOffset = weekday === 0 ? -6 : 1 - weekday;
  return addDateDays(dateKey, mondayOffset);
}

function historyWeekKey(item: Item, view: HistoryItemListView) {
  const timestamp = historyTimestamp(item, view);
  const dateKey = timestamp ? localDateTimeParts(timestamp).date : todayString();
  return weekStartKey(dateKey);
}

function historyWeekLabel(weekStart: string) {
  const currentWeekStart = weekStartKey(todayString());
  const range = `${weekStart} - ${addDateDays(weekStart, 6)}`;
  if (weekStart === currentWeekStart) return `本周 · ${range}`;
  if (weekStart === addDateDays(currentWeekStart, -7)) return `上周 · ${range}`;
  return range;
}

export function groupHistoryItems(items: Item[], view: HistoryItemListView): ItemGroup[] {
  const groups = new Map<string, Item[]>();
  for (const item of sortHistoryItems(items, view)) {
    const weekKey = historyWeekKey(item, view);
    groups.set(weekKey, [...(groups.get(weekKey) ?? []), item]);
  }
  return [...groups.entries()].map(([weekStart, groupItems]) => ({
    label: historyWeekLabel(weekStart),
    items: groupItems,
  }));
}

export function historyWindowForItems(items: Item[], view: HistoryItemListView, minimumCount = HISTORY_BATCH_SIZE): HistoryWindow {
  const sorted = sortHistoryItems(items, view);
  if (minimumCount >= sorted.length) {
    return { items: sorted, visibleCount: sorted.length, totalCount: sorted.length, hasMore: false };
  }

  const boundaryIndex = Math.max(0, minimumCount - 1);
  const boundaryWeek = historyWeekKey(sorted[boundaryIndex], view);
  let visibleCount = Math.max(0, minimumCount);
  while (visibleCount < sorted.length && historyWeekKey(sorted[visibleCount], view) === boundaryWeek) {
    visibleCount += 1;
  }

  return {
    items: sorted.slice(0, visibleCount),
    visibleCount,
    totalCount: sorted.length,
    hasMore: visibleCount < sorted.length,
  };
}

export function matchesItemSearch(item: Item, query: string, projectById?: Map<string, Project>) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  const projectName = item.project_name ?? (item.project_id ? projectById?.get(item.project_id)?.name : '') ?? '';
  const tagText = item.tags.map((tag) => tag.name).join(' ');
  const eventFormat = item.event_format ? eventFormatLabels[item.event_format] : '';
  return [
    item.title,
    item.notes ?? '',
    projectName,
    formatItemSchedule(item),
    tagText,
    item.waiting_on ?? '',
    item.event_location ?? '',
    item.event_url ?? '',
    eventFormat,
    (item.people ?? []).map((person) => `${person.name} ${person.identity ?? ''}`).join(' '),
  ]
    .join(' ')
    .toLowerCase()
    .includes(normalized);
}
