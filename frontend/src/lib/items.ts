import type { Item, Project } from '../api/client';
import { addDaysString, formatItemSchedule, itemDateKey, localDateTimeParts, todayString } from './dates';
import { eventFormatLabels, ItemListView } from './labels';

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

function weekStart(dateText: string): string {
  const [year, month, day] = dateText.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  const weekday = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() - weekday + 1);
  return date.toISOString().slice(0, 10);
}

function weekLabel(start: string): string {
  const [year, month, day] = start.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + 6);
  return `${year}年${month}月${day}日 - ${date.getUTCMonth() + 1}月${date.getUTCDate()}日`;
}

/** Archive groups: completed items use confirmation time and newest completion first. */
export function groupArchivedItems(items: Item[]) {
  const grouped = new Map<string, Item[]>();
  const other: Item[] = [];
  for (const item of items) {
    const timestamp = item.status === 'done' ? item.completed_at : null;
    if (!timestamp) {
      other.push(item);
      continue;
    }
    const key = weekStart(localDateTimeParts(timestamp).date);
    const bucket = grouped.get(key) ?? [];
    bucket.push(item);
    grouped.set(key, bucket);
  }
  const result = [...grouped.entries()]
    .sort(([left], [right]) => right.localeCompare(left))
    .map(([key, bucket]) => ({
      label: `完成于 ${weekLabel(key)}`,
      items: bucket.sort((left, right) => (right.completed_at ?? '').localeCompare(left.completed_at ?? '')),
    }));
  if (other.length > 0) result.push({ label: '其他归档', items: other });
  return result;
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
