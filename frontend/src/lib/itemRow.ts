import type { Item } from '../api/client';
import { formatUpdatedAt } from './dates';
import { formatDuration } from './labels';
import { recurrenceBadge } from './recurrence';

export type RowSegment = { kind: 'person' | 'project' | 'tag' | 'meta'; label: string; color?: string };

/** 左区流动段：协作者 / 已关联项目 / 标签（≤2 + 折叠），非常态才有内容。 */
export function rowSegments(item: Item): RowSegment[] {
  const segments: RowSegment[] = [];
  for (const person of item.people ?? []) {
    segments.push({ kind: 'person', label: `${person.role === 'waiting' ? '等' : '一起'} ${person.name}` });
  }
  if (item.project_name) segments.push({ kind: 'project', label: item.project_name });
  for (const tag of item.tags.slice(0, 2)) segments.push({ kind: 'tag', label: tag.name, color: tag.color });
  if (item.tags.length > 2) segments.push({ kind: 'tag', label: `+${item.tags.length - 2}` });
  const repeat = recurrenceBadge(item);
  if (repeat && item.status !== 'done' && item.status !== 'cancelled') segments.push({ kind: 'meta', label: repeat });
  if (item.estimated_minutes) segments.push({ kind: 'meta', label: `预计 ${formatDuration(item.estimated_minutes)}` });
  return segments;
}

/** 标题 tooltip：备注首行 / 重复 / 预计时长 / 更新与完成时间。 */
export function rowTooltip(item: Item): string {
  const parts: string[] = [];
  const notes = item.notes?.trim().split('\n')[0];
  if (notes) parts.push(notes.length > 60 ? `${notes.slice(0, 60)}…` : notes);
  const repeat = recurrenceBadge(item);
  if (repeat) parts.push(repeat.replace('↻ ', '重复：'));
  if (item.estimated_minutes) parts.push(`预计 ${formatDuration(item.estimated_minutes)}`);
  parts.push(`更新于 ${formatUpdatedAt(item.updated_at)}`);
  if (item.status === 'done' && item.completed_at) parts.push(`完成于 ${formatUpdatedAt(item.completed_at)}`);
  return parts.join(' · ');
}
