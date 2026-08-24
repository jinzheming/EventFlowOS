import type { Item, Project } from '../api/client';
import { addDaysString, formatItemSchedule, itemDateKey, todayString } from './dates';
import { ItemListView } from './labels';

export function groupWorkItems(items: Item[]) {
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

export function groupPersonalItems(items: Item[]) {
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

export function matchesItemSearch(item: Item, query: string, projectById?: Map<string, Project>) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  const projectName = item.project_name ?? (item.project_id ? projectById?.get(item.project_id)?.name : '') ?? '';
  const tagText = item.tags.map((tag) => tag.name).join(' ');
  return [item.title, item.notes ?? '', projectName, formatItemSchedule(item), tagText, item.waiting_on ?? '', (item.people ?? []).map((person) => `${person.name} ${person.identity ?? ''}`).join(' ')]
    .join(' ')
    .toLowerCase()
    .includes(normalized);
}
