import type { Item, Project } from '../api/client';
import { addDaysString, itemDateKey, localDateTimeParts, todayString } from './dates';
import { compareProjects } from './projects';

export interface ReviewBuckets {
  /** active items (non-waiting) whose schedule date is before today */
  overdue: Item[];
  /** waiting items split by follow-up urgency */
  waitingOverdue: Item[];
  waitingToday: Item[];
  waitingFuture: Item[];
  waitingNoDate: Item[];
  /** active projects with no next step recorded */
  projectsNoNextStep: Project[];
  /** active projects whose next_review_at is due (and a next step exists) */
  projectsReviewDue: Project[];
  /** items completed within the last 7 days, newest first */
  doneThisWeek: Item[];
}

function isActive(item: Item) {
  return !item.archived_at && item.status !== 'done' && item.status !== 'cancelled';
}

function byItemDate(a: Item, b: Item) {
  return (itemDateKey(a) ?? '').localeCompare(itemDateKey(b) ?? '');
}

function byFollowUp(a: Item, b: Item) {
  return (a.waiting_follow_up_date ?? '').localeCompare(b.waiting_follow_up_date ?? '');
}

export function buildReview(workItems: Item[], personalItems: Item[], projects: Project[]): ReviewBuckets {
  const today = todayString();
  const weekAgo = addDaysString(-7);
  const all = [...workItems, ...personalItems];
  const active = all.filter(isActive);

  const overdue = active
    .filter((item) => {
      if (item.status === 'waiting') return false;
      const key = itemDateKey(item);
      return key !== null && key < today;
    })
    .sort(byItemDate);

  const waiting = active.filter((item) => item.scope === 'work' && item.status === 'waiting');
  const waitingOverdue = waiting.filter((item) => item.waiting_follow_up_date !== null && item.waiting_follow_up_date < today).sort(byFollowUp);
  const waitingToday = waiting.filter((item) => item.waiting_follow_up_date === today);
  const waitingFuture = waiting.filter((item) => item.waiting_follow_up_date !== null && item.waiting_follow_up_date > today).sort(byFollowUp);
  const waitingNoDate = waiting.filter((item) => !item.waiting_follow_up_date);

  const activeProjects = projects.filter(
    (project) => !project.archived_at && project.status !== 'completed' && project.status !== 'cancelled',
  );
  const projectsNoNextStep = activeProjects.filter((project) => !project.next_step?.trim()).sort(compareProjects);
  const projectsReviewDue = activeProjects
    .filter((project) => Boolean(project.next_step?.trim()) && project.next_review_at !== null && project.next_review_at <= today)
    .sort(compareProjects);

  const doneThisWeek = all
    .filter((item) => {
      if (item.archived_at || item.status !== 'done' || !item.completed_at) return false;
      return localDateTimeParts(item.completed_at).date >= weekAgo;
    })
    .sort((a, b) => (b.completed_at ?? '').localeCompare(a.completed_at ?? ''));

  return { overdue, waitingOverdue, waitingToday, waitingFuture, waitingNoDate, projectsNoNextStep, projectsReviewDue, doneThisWeek };
}

export function reviewOpenCount(buckets: ReviewBuckets): number {
  return (
    buckets.overdue.length +
    buckets.waitingOverdue.length +
    buckets.waitingToday.length +
    buckets.waitingNoDate.length +
    buckets.projectsNoNextStep.length +
    buckets.projectsReviewDue.length
  );
}
