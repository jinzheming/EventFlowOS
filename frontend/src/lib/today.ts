import type { Item, Project } from '../api/client';
import { compareTimedSchedules, timedSchedulesForItem } from './calendar';
import { hasConcreteStartToday, isMustDoToday, isWaitingItem, itemDateKey, localDateTimeParts, todayString } from './dates';
import { compareProjects } from './projects';

export function buildTodayView(items: Item[], projects: Project[]) {
  const today = todayString();
  const activeItems = items.filter((item) => !item.archived_at && item.status !== 'done' && item.status !== 'cancelled');
  const timed = activeItems
    .filter(hasConcreteStartToday)
    .flatMap((item) => {
      const starts = timedSchedulesForItem(item).filter((schedule) => schedule.relation === '开始');
      return starts.length > 0 ? starts : [{ item, time: item.start_at ?? `${item.start_date}T00:00:00`, relation: '开始' as const }];
    })
    .filter((schedule) => localDateTimeParts(schedule.time).date === today)
    .sort(compareTimedSchedules);
  const timedIds = new Set(timed.map((schedule) => schedule.item.id));
  const byDateKey = (a: Item, b: Item) => (itemDateKey(a) ?? '').localeCompare(itemDateKey(b) ?? '');
  const waiting = activeItems.filter((item) => {
    if (!isWaitingItem(item)) return false;
    return !item.waiting_follow_up_date || item.waiting_follow_up_date <= today;
  });
  const completedToday = items.filter(
    (item) => item.status === 'done' && item.completed_at && localDateTimeParts(item.completed_at).date === today,
  ).length;
  return {
    timed,
    due: activeItems.filter((item) => isMustDoToday(item) && !timedIds.has(item.id)).sort(byDateKey),
    waiting,
    completedToday,
    riskProjects: projects
      .filter(
        (project) =>
          !project.archived_at &&
          project.status !== 'completed' &&
          project.status !== 'cancelled' &&
          (project.health === 'at_risk' || project.health === 'blocked' || Boolean(project.next_review_at && project.next_review_at <= today)),
      )
      .sort(compareProjects),
    unscheduled: activeItems.filter((item) => !itemDateKey(item)).sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()),
  };
}
