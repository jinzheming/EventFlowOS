import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useMemo, useState } from 'react';
import { CheckCircle2, Circle as CircleIcon } from 'lucide-react';
import { api, HabitWeek, Item, Scope, Session } from '../api/client';
import { PersonalItemDrawer } from '../components/PersonalItemDrawer';
import { ProjectDrawer } from '../components/ProjectDrawer';
import { QuickFilterBar } from '../components/QuickFilterBar';
import { TodayItemButton, TodayProjectRow, TodaySection, TodayTimedRow } from '../components/TodayRows';
import { WorkItemDrawer } from '../components/WorkItemDrawer';
import { usePatchItem, useSaveItemWithReminder } from '../hooks/useItemActions';
import { usePatchProject } from '../hooks/useProjectActions';
import { useToggleDone } from '../hooks/useToggleDone';
import { useUndo } from '../hooks/useUndo';
import { todayString } from '../lib/dates';
import { buildPersonalPayload, buildWorkPayload, emptyPersonalDraft, emptyWorkDraft } from '../lib/drafts';
import { ItemQuickFilter, matchesQuickFilter, todayQuickFilters } from '../lib/itemFilters';
import { buildProjectPatch } from '../lib/projects';
import { buildTodayView } from '../lib/today';

export function TodayPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.projects });
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });
  const focusToday = useQuery({ queryKey: ['focus', 'today'], queryFn: api.focusToday, refetchInterval: 60000 });
  const habits = useQuery({ queryKey: ['habits', 'week'], queryFn: () => api.habitsWeek(0) });
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [quickFilter, setQuickFilter] = useState<ItemQuickFilter>('all');
  const [quickTitle, setQuickTitle] = useState('');
  const [quickScope, setQuickScope] = useState<Scope>('work');
  const allItems = useMemo(() => [...(workItems.data ?? []), ...(personalItems.data ?? [])], [personalItems.data, workItems.data]);
  const selectedItem = allItems.find((item) => item.id === selectedItemId) ?? null;
  const selectedProject = projects.data?.find((project) => project.id === selectedProjectId) ?? null;
  const selectedProjectItems = useQuery({
    queryKey: ['project-items', selectedProject?.id],
    queryFn: () => api.projectItems(selectedProject!.id),
    enabled: !!selectedProject,
  });
  const today = useMemo(() => buildTodayView(allItems, projects.data ?? []), [allItems, projects.data]);
  const dueItems = useMemo(
    () => today.due.filter((item) => matchesQuickFilter(item, quickFilter)),
    [today.due, quickFilter],
  );

  function invalidateToday(projectId?: string) {
    queryClient.invalidateQueries({ queryKey: ['items', 'work'] });
    queryClient.invalidateQueries({ queryKey: ['items', 'personal'] });
    queryClient.invalidateQueries({ queryKey: ['projects'] });
    if (projectId) queryClient.invalidateQueries({ queryKey: ['project-items', projectId] });
    queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
  }

  const patchItem = usePatchItem(session, (item) => {
    setSelectedItemId(item.id);
    invalidateToday(item.project_id ?? undefined);
  });

  const saveItem = useSaveItemWithReminder(session, (item) => {
    setSelectedItemId(item.id);
    invalidateToday(item.project_id ?? undefined);
  });

  const patchProject = usePatchProject(session, (project) => {
    setSelectedProjectId(project.id);
    invalidateToday(project.id);
  });

  const createToday = useMutation({
    mutationFn: async () => {
      const title = quickTitle.trim();
      if (quickScope === 'work') {
        return api.createItem(session.csrf_token, buildWorkPayload({ ...emptyWorkDraft(), title, start_date: todayString() }));
      }
      return api.createItem(session.csrf_token, buildPersonalPayload({ ...emptyPersonalDraft(), title, start_date: todayString() }));
    },
    onSuccess: (item) => {
      setQuickTitle('');
      setSelectedItemId(item.id);
      invalidateToday(item.project_id ?? undefined);
    },
  });

  const undo = useUndo();
  const toggleWork = useToggleDone(session, 'work');
  const togglePersonal = useToggleDone(session, 'personal');

  // 软删除：进回收站（设置页），撤销即恢复
  function deleteFromDrawer(item: Item) {
    void api.deleteItem(session.csrf_token, item.id).then(() => {
      setSelectedItemId(null);
      invalidateToday(item.project_id ?? undefined);
      queryClient.invalidateQueries({ queryKey: ['items-trash'] });
      undo.pushUndo(`已删除「${item.title}」（回收站可恢复）`, () => {
        void api.restoreDeletedItem(session.csrf_token, item.id).then(() => {
          invalidateToday(item.project_id ?? undefined);
          queryClient.invalidateQueries({ queryKey: ['items-trash'] });
        });
      });
    });
  }

  function toggleInline(item: Item) {
    const toggle = item.scope === 'work' ? toggleWork : togglePersonal;
    const previousStatus = item.status;
    toggle.mutate(
      { item, next: 'done' },
      {
        onSuccess: (updated) =>
          undo.pushUndo(`已完成「${item.title}」`, () => toggle.mutate({ item: updated, next: previousStatus })),
      },
    );
  }

  const toggleCheckin = useMutation({
    mutationFn: (habit: HabitWeek) =>
      habit.today_done ? api.undoCheckin(session.csrf_token, habit.item_id, todayString()) : api.checkin(session.csrf_token, habit.item_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['habits'] }),
  });

  return (
    <section className="page today-page">
      <header className="page-header">
        <div>
          <h1>今日</h1>
          <p>
            今日概览 · 已完成 {today.completedToday} 项
            {focusToday.data && focusToday.data.total_seconds > 0 && ` · 今日专注 ${Math.floor(focusToday.data.total_seconds / 3600)}小时${Math.round((focusToday.data.total_seconds % 3600) / 60)}分`}
          </p>
        </div>
      </header>
      <form
        className="personal-quick-add"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (quickTitle.trim()) createToday.mutate();
        }}
      >
        <div className="quick-add-scope">
          <span className="muted">归入</span>
          <button className={quickScope === 'work' ? 'chip active' : 'chip'} type="button" onClick={() => setQuickScope('work')}>
            工作
          </button>
          <button className={quickScope === 'personal' ? 'chip active' : 'chip'} type="button" onClick={() => setQuickScope('personal')}>
            个人
          </button>
        </div>
        <div className="quick-add-row">
          <input placeholder="添加今日事项（默认今天开始，完整创建按 ⌘K）" value={quickTitle} onChange={(event) => setQuickTitle(event.target.value)} />
          <button className="primary" type="submit" disabled={!quickTitle.trim() || createToday.isPending}>
            添加到今天
          </button>
        </div>
      </form>

      {habits.data && habits.data.length > 0 && (
        <section className="habit-strip" aria-label="今日习惯打卡">
          {habits.data.map((habit) => (
            <button
              key={habit.item_id}
              className={habit.today_done ? 'habit-chip done' : 'habit-chip'}
              type="button"
              disabled={toggleCheckin.isPending}
              title={`${habit.title} · 连续 ${habit.streak} 天 · 本周 ${habit.week_done}/${habit.week_target}`}
              onClick={() => toggleCheckin.mutate(habit)}
            >
              {habit.today_done ? <CheckCircle2 size={15} /> : <CircleIcon size={15} />}
              <span>{habit.title}</span>
              {habit.streak > 0 && <em>🔥{habit.streak}</em>}
            </button>
          ))}
        </section>
      )}
      {createToday.isError && <p className="error-line">{createToday.error.message}</p>}
      <QuickFilterBar value={quickFilter} options={todayQuickFilters} onChange={setQuickFilter} />
      <div className="today-grid">
        <TodaySection title="现在 / 接下来" count={today.timed.length}>
          {today.timed.map((schedule) => (
            <TodayTimedRow item={schedule.item} time={schedule.time} key={`${schedule.item.id}-${schedule.time}`} onOpen={() => setSelectedItemId(schedule.item.id)} onToggleDone={() => toggleInline(schedule.item)} />
          ))}
        </TodaySection>
        <TodaySection title={quickFilter === 'overdue' ? '仅逾期' : '今天必须处理'} count={dueItems.length}>
          {dueItems.map((item) => (
            <TodayItemButton item={item} key={item.id} onOpen={() => setSelectedItemId(item.id)} onToggleDone={() => toggleInline(item)} />
          ))}
        </TodaySection>
        <TodaySection title="等待跟进" count={today.waiting.length}>
          {today.waiting.map((item) => (
            <TodayItemButton item={item} key={item.id} onOpen={() => setSelectedItemId(item.id)} onToggleDone={() => toggleInline(item)} />
          ))}
        </TodaySection>
        <TodaySection title="阻塞项目" count={today.riskProjects.length}>
          {today.riskProjects.map((project) => (
            <TodayProjectRow project={project} key={project.id} onOpen={() => setSelectedProjectId(project.id)} />
          ))}
        </TodaySection>
        <details className="today-unscheduled">
          <summary>
            未排期 <span>{today.unscheduled.length}</span>
            <a className="today-unscheduled-link" href="#/work">去工作事项</a>
            <a className="today-unscheduled-link" href="#/personal">去个人事项</a>
          </summary>
          <div className="today-list">
            {today.unscheduled.length === 0 && <p className="empty">暂无内容</p>}
            {today.unscheduled.map((item) => (
              <TodayItemButton item={item} key={item.id} onOpen={() => setSelectedItemId(item.id)} onToggleDone={() => toggleInline(item)} />
            ))}
          </div>
        </details>
      </div>

      {selectedItem?.scope === 'work' && (
        <WorkItemDrawer
          item={selectedItem}
          projects={projects.data ?? []}
          session={session}
          saving={saveItem.isPending || patchItem.isPending}
          error={saveItem.error?.message ?? patchItem.error?.message}
          onClose={() => setSelectedItemId(null)}
          onSave={(draft, reminderTouched, tagIds) =>
            saveItem.mutate({ item: selectedItem, draft, reminderTouched, tagIds })
          }
          onStatus={(status) => patchItem.mutate({ item: selectedItem, payload: { status } })}
          onReschedule={(payload) => patchItem.mutate({ item: selectedItem, payload })}
          onDelete={() => deleteFromDrawer(selectedItem)}
        />
      )}
      {selectedItem?.scope === 'personal' && (
        <PersonalItemDrawer
          item={selectedItem}
          session={session}
          saving={saveItem.isPending || patchItem.isPending}
          error={saveItem.error?.message ?? patchItem.error?.message}
          onClose={() => setSelectedItemId(null)}
          onSave={(draft, reminderTouched, tagIds) =>
            saveItem.mutate({ item: selectedItem, draft, reminderTouched, tagIds })
          }
          onStatus={(status) => patchItem.mutate({ item: selectedItem, payload: { status } })}
          onReschedule={(payload) => patchItem.mutate({ item: selectedItem, payload })}
          onDelete={() => deleteFromDrawer(selectedItem)}
        />
      )}
      {selectedProject && (
        <ProjectDrawer
          project={selectedProject}
          items={selectedProjectItems.data ?? []}
          session={session}
          saving={patchProject.isPending}
          error={patchProject.error?.message}
          onClose={() => setSelectedProjectId(null)}
          onSave={(draft) => patchProject.mutate({ project: selectedProject, payload: buildProjectPatch(draft) })}
          onStatus={(status) => patchProject.mutate({ project: selectedProject, payload: { status } })}
        />
      )}
    </section>
  );
}
