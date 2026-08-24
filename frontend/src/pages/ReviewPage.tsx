import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CircleAlert, FolderKanban, Hourglass, PartyPopper } from 'lucide-react';
import { useMemo, useState } from 'react';
import { api, FocusCalibration, HabitWeek, Item, Project, Session } from '../api/client';
import { ItemRowShell, RowPriorityMark, RowSegments, RowTimeSlot, RowWaitingMark, rowTooltip } from '../components/ItemRow';
import { PersonalItemDrawer } from '../components/PersonalItemDrawer';
import { WorkItemDrawer } from '../components/WorkItemDrawer';
import { usePatchItem, useSaveItemWithReminder } from '../hooks/useItemActions';
import { useToggleDone } from '../hooks/useToggleDone';
import { useUndo } from '../hooks/useUndo';
import { itemDateKey, todayString } from '../lib/dates';
import { projectHealthLabels, scopeLabel } from '../lib/labels';
import { buildReview, ReviewBuckets } from '../lib/review';

export function ReviewPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.projects });
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });
  const buckets = useMemo(
    () => buildReview(workItems.data ?? [], personalItems.data ?? [], projects.data ?? []),
    [workItems.data, personalItems.data, projects.data],
  );
  const habits = useQuery({ queryKey: ['habits', 'week'], queryFn: () => api.habitsWeek(0) });
  const habitsLast = useQuery({ queryKey: ['habits', 'week', 1], queryFn: () => api.habitsWeek(1) });
  const calibration = useQuery({ queryKey: ['focus', 'week'], queryFn: api.focusWeek });
  const today = todayString();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const allItems = useMemo(() => [...(workItems.data ?? []), ...(personalItems.data ?? [])], [workItems.data, personalItems.data]);
  const selected = allItems.find((item) => item.id === selectedId) ?? null;

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['items'] });
    queryClient.invalidateQueries({ queryKey: ['projects'] });
  }
  const patchItem = usePatchItem(session, (item) => {
    setSelectedId(item.id);
    invalidate();
  });
  const saveItem = useSaveItemWithReminder(session, (item) => {
    setSelectedId(item.id);
    invalidate();
  });
  const undo = useUndo();

  function deleteFromDrawer(item: Item) {
    void api.deleteItem(session.csrf_token, item.id).then(() => {
      setSelectedId(null);
      invalidate();
      queryClient.invalidateQueries({ queryKey: ['items-trash'] });
      undo.pushUndo(`已删除「${item.title}」（回收站可恢复）`, () => {
        void api.restoreDeletedItem(session.csrf_token, item.id).then(() => {
          invalidate();
          queryClient.invalidateQueries({ queryKey: ['items-trash'] });
        });
      });
    });
  }

  const waitingTotal =
    buckets.waitingOverdue.length + buckets.waitingToday.length + buckets.waitingFuture.length + buckets.waitingNoDate.length;
  const projectTotal = buckets.projectsNoNextStep.length + buckets.projectsReviewDue.length;
  const pendingTotal = buckets.overdue.length + waitingTotal + projectTotal;

  const summary =
    pendingTotal > 0
      ? `本周待处理：${[
          buckets.overdue.length > 0 ? `${buckets.overdue.length} 逾期` : null,
          waitingTotal > 0 ? `${waitingTotal} 等待` : null,
          projectTotal > 0 ? `${projectTotal} 项目` : null,
        ]
          .filter(Boolean)
          .join(' · ')}`
      : '✓ 本周清爽，无遗留';

  return (
    <div className="page review-page">
      <header className="page-header">
        <h1>周复盘</h1>
        <p>{summary}（基准 {today}）</p>
      </header>

      <div className="today-grid">
        <OverdueCard session={session} items={buckets.overdue} onOpen={setSelectedId} order={1} />
        <WaitingCard session={session} buckets={buckets} onOpen={setSelectedId} order={2} />
        <ProjectCheckCard buckets={buckets} order={3} />
        <InsightsCard habits={habits.data ?? []} habitsLast={habitsLast.data ?? []} calibration={calibration.data} overdue={buckets.overdue} />
        <DoneCard items={buckets.doneThisWeek} />
      </div>

      {selected?.scope === 'work' && (
        <WorkItemDrawer
          item={selected}
          session={session}
          projects={projects.data ?? []}
          saving={saveItem.isPending || patchItem.isPending}
          error={saveItem.error?.message ?? patchItem.error?.message}
          onClose={() => setSelectedId(null)}
          onSave={(draft, reminderTouched, tagIds) => saveItem.mutate({ item: selected, draft, reminderTouched, tagIds })}
          onStatus={(status) => patchItem.mutate({ item: selected, payload: { status } })}
          onReschedule={(payload) => patchItem.mutate({ item: selected, payload })}
          onDelete={() => deleteFromDrawer(selected)}
        />
      )}
      {selected?.scope === 'personal' && (
        <PersonalItemDrawer
          item={selected}
          session={session}
          saving={saveItem.isPending || patchItem.isPending}
          error={saveItem.error?.message ?? patchItem.error?.message}
          onClose={() => setSelectedId(null)}
          onSave={(draft, reminderTouched, tagIds) => saveItem.mutate({ item: selected, draft, reminderTouched, tagIds })}
          onStatus={(status) => patchItem.mutate({ item: selected, payload: { status } })}
          onReschedule={(payload) => patchItem.mutate({ item: selected, payload })}
          onDelete={() => deleteFromDrawer(selected)}
        />
      )}
    </div>
  );
}

function OverdueCard({ session, items, onOpen, order }: { session: Session; items: Item[]; onOpen: (id: string) => void; order: number }) {
  return (
    <section className="today-card">
      <h2>
        <CircleAlert size={16} /> {order} 逾期遗留 <span>{items.length}</span>
      </h2>
      <div className="today-list">
        {items.length === 0 && <p className="empty">✓ 没有逾期事项</p>}
        {items.map((item) => (
          <ReviewRow key={item.id} session={session} item={item} onOpen={onOpen} overdue />
        ))}
      </div>
    </section>
  );
}

function WaitingCard({ session, buckets, onOpen, order }: { session: Session; buckets: ReviewBuckets; onOpen: (id: string) => void; order: number }) {
  const groups: Array<{ label: string; items: Item[]; urgent: boolean }> = [
    { label: '跟进已超期', items: buckets.waitingOverdue, urgent: true },
    { label: '今天该跟进', items: buckets.waitingToday, urgent: true },
    { label: '未设跟进日期', items: buckets.waitingNoDate, urgent: false },
    { label: '未来跟进', items: buckets.waitingFuture, urgent: false },
  ];
  const total = groups.reduce((sum, group) => sum + group.items.length, 0);
  return (
    <section className="today-card">
      <h2>
        <Hourglass size={16} /> {order} 等待跟进 <span>{total}</span>
      </h2>
      <div className="today-list">
        {total === 0 && <p className="empty">✓ 没有等待中的事项</p>}
        {groups.map(
          (group) =>
            group.items.length > 0 && (
              <div className="review-subgroup" key={group.label}>
                <small className={group.urgent ? 'review-subgroup-label urgent' : 'review-subgroup-label'}>{group.label}</small>
                {group.items.map((item) => (
                  <ReviewRow key={item.id} session={session} item={item} onOpen={onOpen} overdue={group.urgent} />
                ))}
              </div>
            ),
        )}
      </div>
    </section>
  );
}

function ProjectCheckCard({ buckets, order }: { buckets: ReviewBuckets; order: number }) {
  const rows: Array<{ project: Project; reason: string }> = [
    ...buckets.projectsNoNextStep.map((project) => ({ project, reason: '缺下一步' })),
    ...buckets.projectsReviewDue.map((project) => ({ project, reason: `待复盘 · ${project.next_review_at}` })),
  ];
  return (
    <section className="today-card">
      <h2>
        <FolderKanban size={16} /> {order} 项目检查 <span>{rows.length}</span>
      </h2>
      <div className="today-list">
        {rows.length === 0 && <p className="empty">✓ 项目都有下一步且在复盘周期内</p>}
        {rows.map(({ project, reason }) => (
          <div
            className="today-row"
            key={project.id}
            role="button"
            tabIndex={0}
            onClick={() => (window.location.hash = '/projects')}
            onKeyDown={(event) => event.key === 'Enter' && (window.location.hash = '/projects')}
          >
            <strong>{project.name}</strong>
            <small>
              {projectHealthLabels[project.health]} · {reason}
            </small>
          </div>
        ))}
      </div>
    </section>
  );
}

function ReviewRow({ session, item, onOpen, overdue }: { session: Session; item: Item; onOpen: (id: string) => void; overdue?: boolean }) {
  const toggle = useToggleDone(session, item.scope);
  return (
    <ItemRowShell
      className={overdue ? 'review-row overdue' : 'review-row'}
      done={false}
      tooltip={rowTooltip(item)}
      onOpen={() => onOpen(item.id)}
      check={{ done: false, onToggle: () => toggle.mutate({ item, next: 'done' }) }}
      flow={
        <>
          <span className="row-scope">{scopeLabel(item.scope)}</span>
          <strong className="row-title">{item.title}</strong>
          <RowPriorityMark item={item} />
          <RowWaitingMark item={item} />
          <RowSegments item={item} />
        </>
      }
      timeslot={<RowTimeSlot item={item} />}
    />
  );
}

function DoneCard({ items }: { items: Item[] }) {
  return (
    <section className="today-card">
      <h2>
        <PartyPopper size={16} /> 近 7 天已完成 <span>{items.length}</span>
      </h2>
      <div className="today-list">
        {items.length === 0 && <p className="empty">本周还没有完成记录</p>}
        {items.length > 0 && (
          <details className="review-done-details">
            <summary>查看完成清单（{items.length} 条）</summary>
            {items.map((item) => (
              <div className="today-row done" key={item.id}>
                <strong>{item.title}</strong>
                <small>
                  {scopeLabel(item.scope)} · 完成于 {item.completed_at?.slice(0, 10)}
                </small>
              </div>
            ))}
          </details>
        )}
      </div>
    </section>
  );
}

type Insight = { tone: 'warning' | 'danger' | 'accent'; text: string };

/** 只产出能改变「下次行为」的洞察；每条必须带动作。 */
function buildInsights(habits: HabitWeek[], habitsLast: HabitWeek[], calibration: FocusCalibration | undefined, overdue: Item[]): Insight[] {
  const out: Insight[] = [];

  // 1) 预估校准系数：系统性偏差才报（|偏差|>15% 且样本≥3）
  if (calibration && calibration.calibrated_count >= 3 && calibration.estimated_seconds > 0) {
    const ratio = calibration.calibrated_actual_seconds / calibration.estimated_seconds - 1;
    if (Math.abs(ratio) > 0.15) {
      const pct = Math.round(Math.abs(ratio) * 100);
      const factor = (calibration.calibrated_actual_seconds / calibration.estimated_seconds).toFixed(1);
      out.push({
        tone: 'warning',
        text: `预估校准：本周专注系统性${ratio > 0 ? '低估' : '高估'} ${pct}% → 以后预估请 ×${factor}`,
      });
    }
  }

  // 2) 习惯连续两周未达标才干预（单周波动是噪音）
  const lastByTitle = new Map(habitsLast.map((h) => [h.title, h]));
  for (const habit of habits.filter((h) => h.recurrence_freq === 'daily')) {
    const prev = lastByTitle.get(habit.title);
    const missedThis = habit.week_done < habit.week_target;
    const missedPrev = prev ? prev.week_done < prev.week_target : false;
    if (missedThis && missedPrev) {
      out.push({
        tone: 'warning',
        text: `习惯断档：「${habit.title}」连续 2 周未达标（${prev!.week_done}/${prev!.week_target} → ${habit.week_done}/${habit.week_target}）→ 降频还是换执行策略？`,
      });
    }
  }

  // 3) 逾期尸检：最老逾期的年龄驱动处置决策
  if (overdue.length > 0) {
    const dated = overdue.filter((item) => itemDateKey(item) !== null);
    if (dated.length > 0) {
      const oldest = dated.reduce((a, b) => ((itemDateKey(a) ?? '') < (itemDateKey(b) ?? '') ? a : b));
      const ageDays = Math.floor((Date.parse(todayString()) - Date.parse(itemDateKey(oldest) as string)) / 86400000);
      if (ageDays >= 14) {
      out.push({
        tone: 'danger',
        text: `逾期尸检：「${oldest.title}」已逾期 ${ageDays} 天 → 点开删除还是改期复活？`,
      });
      }
    }
  }

  return out.slice(0, 3);
}

function InsightsCard({
  habits,
  habitsLast,
  calibration,
  overdue,
}: {
  habits: HabitWeek[];
  habitsLast: HabitWeek[];
  calibration?: FocusCalibration;
  overdue: Item[];
}) {
  const lines = buildInsights(habits, habitsLast, calibration, overdue);
  return (
    <section className="today-card insights-card">
      <h2>本周洞察</h2>
      {lines.length === 0 && <p className="empty">本周数据平稳，无异常模式</p>}
      <ul>
        {lines.map((line) => (
          <li key={line.text} className={`tone-${line.tone}`}>
            {line.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
