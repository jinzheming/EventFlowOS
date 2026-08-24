import type { ItemStatus, Priority, ProjectHealth, ProjectStatus, Scope } from '../api/client';

export type ItemListView = 'current' | 'done' | 'archived';

export const itemViewLabels: Record<ItemListView, string> = {
  current: '当前',
  done: '已完成',
  archived: '归档',
};

export const statusLabels: Record<ItemStatus, string> = {
  inbox: '收集箱',
  planned: '待处理',
  in_progress: '进行中',
  waiting: '等待他人',
  done: '已完成',
  cancelled: '已取消',
};

export const priorityLabels: Record<Priority, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急',
};

export const projectStatusLabels: Record<ProjectStatus, string> = {
  planned: '进行中',
  active: '进行中',
  on_hold: '暂停',
  completed: '已完成',
  cancelled: '已取消',
};

export const projectHealthLabels: Record<ProjectHealth, string> = {
  unknown: '未评估',
  on_track: '正常',
  at_risk: '有风险',
  blocked: '阻塞',
};

export const reminderOffsets = [
  { value: 0, label: '准时' },
  { value: 15, label: '提前 15 分钟' },
  { value: 60, label: '提前 1 小时' },
  { value: 1440, label: '提前 1 天' },
];

export function scopeLabel(scope: Scope) {
  return scope === 'work' ? '工作' : '个人';
}

/** 预计时长格式:null→null;90→1.5 小时;45→45 分钟;150→2 小时 30 分钟 */
export function formatDuration(minutes: number | null): string | null {
  if (!minutes || minutes <= 0) return null;
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = minutes / 60;
  if (minutes % 60 === 0) return `${hours} 小时`;
  const whole = Math.floor(hours);
  const rest = minutes % 60;
  if (rest === 30) return `${whole}.5 小时`;
  return `${whole} 小时 ${rest} 分钟`;
}
