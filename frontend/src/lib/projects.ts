import type { Item, Project, ProjectHealth, ProjectStatus } from '../api/client';
import { formatUpdatedAt, isDueTodayOrEarlier } from './dates';
import { projectHealthLabels, projectStatusLabels } from './labels';

export type ProjectDraft = {
  name: string;
  status: ProjectStatus;
  health: ProjectHealth;
  next_step: string;
  due_date: string;
  risk_summary: string;
  group_id: string;
};

export function projectDraftFromProject(project: Project): ProjectDraft {
  return {
    name: project.name,
    status: project.status === 'planned' ? 'active' : project.status,
    health: project.health,
    next_step: project.next_step ?? '',
    due_date: project.due_date ?? '',
    risk_summary: project.risk_summary ?? '',
    group_id: project.group_id ?? '',
  };
}

export function buildProjectPatch(draft: ProjectDraft): Partial<Project> {
  return {
    name: draft.name.trim(),
    status: draft.status,
    health: draft.health,
    next_step: draft.next_step.trim() || null,
    due_date: draft.due_date || null,
    risk_summary: draft.risk_summary.trim() || null,
    group_id: draft.group_id || null,
  };
}

export function groupProjects(projects: Project[]) {
  const sorted = [...projects].filter((project) => !project.archived_at).sort(compareProjects);
  return [
    { label: '进行中', projects: sorted.filter((project) => project.status === 'active' || project.status === 'planned') },
    { label: '暂停', projects: sorted.filter((project) => project.status === 'on_hold') },
    { label: '已完成', projects: sorted.filter((project) => project.status === 'completed') },
    { label: '已取消', projects: sorted.filter((project) => project.status === 'cancelled') },
  ];
}

export function filterProjects(projects: Project[], query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return projects;
  return projects.filter((project) =>
    [project.name, project.next_step ?? '', project.risk_summary ?? '', projectStatusLabels[project.status], projectHealthLabels[project.health]]
      .join(' ')
      .toLowerCase()
      .includes(normalized),
  );
}

export function compareProjects(a: Project, b: Project) {
  const healthOrder: Record<ProjectHealth, number> = { blocked: 0, at_risk: 1, unknown: 2, on_track: 3 };
  const healthDiff = healthOrder[a.health] - healthOrder[b.health];
  if (healthDiff !== 0) return healthDiff;
  if (a.due_date && !b.due_date) return -1;
  if (!a.due_date && b.due_date) return 1;
  if (a.due_date && b.due_date && a.due_date !== b.due_date) return a.due_date.localeCompare(b.due_date);
  return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
}

export function summarizeProjectItems(project: Project, items: Item[]) {
  const active = items.filter((item) => !item.archived_at && item.status !== 'done' && item.status !== 'cancelled');
  const dueNow = active.filter(isDueTodayOrEarlier).length;
  const updates = [project.updated_at, ...items.map((item) => item.updated_at)].sort();
  const latest = updates[updates.length - 1] ?? project.updated_at;
  const flags: string[] = [];
  if (dueNow > 0) flags.push('存在今天/逾期事项');
  if (!project.next_step?.trim()) flags.push('缺少下一步');
  if (active.length === 0 && project.status !== 'completed' && project.status !== 'cancelled') flags.push('暂无未完成事项');
  // Progress: manual mode uses the stored percent; otherwise derive from linked items.
  let progressPercent = project.progress_mode === 'manual' ? project.progress_percent : null;
  if (progressPercent === null) {
    const countable = items.filter((item) => item.status !== 'cancelled');
    const done = countable.filter((item) => item.status === 'done').length;
    progressPercent = countable.length > 0 ? Math.round((done * 100) / countable.length) : null;
  }
  return {
    open: active.length,
    dueNow,
    waiting: active.filter((item) => item.status === 'waiting').length,
    updatedLabel: formatUpdatedAt(latest),
    progressPercent,
    flags,
  };
}

export function formatProjectDue(project: Project) {
  return project.due_date ?? '未设置';
}
