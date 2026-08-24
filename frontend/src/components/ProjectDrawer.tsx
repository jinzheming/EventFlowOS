import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Plus, Save, Trash2, X } from 'lucide-react';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { api, Item, Milestone, Project, ProjectHealth, ProjectStatus, Session } from '../api/client';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { formatItemSchedule } from '../lib/dates';
import { ProjectDraft, projectDraftFromProject, summarizeProjectItems } from '../lib/projects';
import { projectHealthLabels, projectStatusLabels } from '../lib/labels';

export function ProjectDrawer({
  project,
  items,
  session,
  saving,
  error,
  onClose,
  onSave,
  onStatus,
}: {
  project: Project;
  items: Item[];
  session: Session;
  saving: boolean;
  error?: string;
  onClose: () => void;
  onSave: (draft: ProjectDraft) => void;
  onStatus: (status: ProjectStatus) => void;
}) {
  const [draft, setDraft] = useState<ProjectDraft>(() => projectDraftFromProject(project));
  const drawerRef = useRef<HTMLElement>(null);
  useDialogA11y(drawerRef, onClose);

  useEffect(() => {
    setDraft(projectDraftFromProject(project));
  }, [project]);

  const queryClient = useQueryClient();
  const groups = useQuery({ queryKey: ['project-groups'], queryFn: () => api.projectGroups() });
  const [newGroupName, setNewGroupName] = useState<string | null>(null);
  const createGroup = useMutation({
    mutationFn: (name: string) => api.createProjectGroup(session.csrf_token, { name }),
    onSuccess: (group) => {
      setDraft((current) => ({ ...current, group_id: group.id }));
      setNewGroupName(null);
      queryClient.invalidateQueries({ queryKey: ['project-groups'] });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.name.trim()) onSave(draft);
  }

  return (
    <aside className="detail-drawer project-drawer" role="dialog" aria-modal="true" aria-labelledby="project-drawer-title" ref={drawerRef}>
      <form onSubmit={submit}>
        <header className="panel-header">
          <div>
            <p className="eyebrow">Project</p>
            <h2 id="project-drawer-title">项目详情</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭">
            <X size={16} />
          </button>
        </header>
        <label>
          项目名称
          <input data-autofocus value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
        </label>
        <div className="field-grid">
          <label>
            状态
            <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as ProjectStatus })}>
              {(['active', 'on_hold', 'completed', 'cancelled'] as ProjectStatus[]).map((status) => (
                <option value={status} key={status}>
                  {projectStatusLabels[status]}
                </option>
              ))}
            </select>
          </label>
          <label>
            健康度
            <select value={draft.health} onChange={(event) => setDraft({ ...draft, health: event.target.value as ProjectHealth })}>
              {Object.entries(projectHealthLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          下一步
          <input value={draft.next_step} onChange={(event) => setDraft({ ...draft, next_step: event.target.value })} />
        </label>
        <label>
          截止日期
          <input type="date" value={draft.due_date} onChange={(event) => setDraft({ ...draft, due_date: event.target.value })} />
        </label>
        <label>
          分组
          <select
            value={newGroupName !== null ? '__new__' : draft.group_id}
            onChange={(event) => {
              if (event.target.value === '__new__') setNewGroupName('');
              else {
                setNewGroupName(null);
                setDraft({ ...draft, group_id: event.target.value });
              }
            }}
          >
            <option value="">未分类</option>
            {(groups.data ?? []).map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
            <option value="__new__">+ 新建分组…</option>
          </select>
        </label>
        {newGroupName !== null && (
          <div className="group-inline-create">
            <input placeholder="新分组名称，回车创建" value={newGroupName} onChange={(event) => setNewGroupName(event.target.value)} />
            <button
              className="ghost sm"
              type="button"
              disabled={!newGroupName.trim() || createGroup.isPending}
              onClick={() => createGroup.mutate(newGroupName.trim())}
            >
              <Plus size={14} /> 创建并选中
            </button>
            {createGroup.isError && <p className="error-line">{createGroup.error.message}</p>}
          </div>
        )}
        <label>
          风险/备注
          <textarea value={draft.risk_summary} onChange={(event) => setDraft({ ...draft, risk_summary: event.target.value })} />
        </label>
        <section className="linked-items project-linked-items">
          <ProjectItemSummary project={project} items={items} />
          <h2>关联工作事项</h2>
          {items.length === 0 && <p className="empty">暂无关联工作事项</p>}
          {items.map((item) => (
            <article className="project-linked-row" key={item.id}>
              <span className={item.status === 'done' ? 'check done' : 'check'}>{item.status === 'done' ? <Check size={14} /> : null}</span>
              <div className="row-main">
                <strong>{item.title}</strong>
                <span>{formatItemSchedule(item)}</span>
              </div>
            </article>
          ))}
        </section>
        <MilestoneSection project={project} session={session} />
        {error && <p className="error-line">{error}</p>}
        <footer className="panel-actions split">
          <button className="secondary" type="button" onClick={() => onStatus(project.status === 'completed' ? 'active' : 'completed')}>
            {project.status === 'completed' ? '重新打开' : '完成项目'}
          </button>
          <button className="danger" type="button" onClick={() => onStatus('cancelled')} disabled={project.status === 'cancelled'}>
            取消项目
          </button>
          <button className="primary" type="submit" disabled={!draft.name.trim() || saving}>
            <Save size={16} /> 保存
          </button>
        </footer>
      </form>
    </aside>
  );
}

export function ProjectItemSummary({ project, items }: { project: Project; items: Item[] }) {
  const summary = summarizeProjectItems(project, items);
  return (
    <section className="project-summary-panel">
      <h2>自动汇总</h2>
      <div className="summary-grid">
        <span>未完成 {summary.open}</span>
        <span>今天/逾期 {summary.dueNow}</span>
        <span>等待他人 {summary.waiting}</span>
        <span>最近更新 {summary.updatedLabel}</span>
      </div>
      {summary.progressPercent !== null && (
        <div className="project-progress" aria-label={`完成度 ${summary.progressPercent}%`}>
          <div className="project-progress-track">
            <div className="project-progress-fill" style={{ width: `${summary.progressPercent}%` }} />
          </div>
          <span>{summary.progressPercent}%</span>
        </div>
      )}
      {summary.flags.length > 0 && <p className="hint">{summary.flags.join(' · ')}</p>}
    </section>
  );
}

// 里程碑管理：列表勾选完成 / 添加 / 删除。注意位于外层 <form> 内，所有按钮必须 type="button"。
function MilestoneSection({ project, session }: { project: Project; session: Session }) {
  const queryClient = useQueryClient();
  const milestones = useQuery({
    queryKey: ['project-milestones', project.id],
    queryFn: () => api.milestones(project.id),
  });
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [error, setError] = useState<string | null>(null);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['project-milestones', project.id] });
    queryClient.invalidateQueries({ queryKey: ['projects'] });
    queryClient.invalidateQueries({ queryKey: ['calendar'] });
  }

  const create = useMutation({
    mutationFn: () => api.createMilestone(session.csrf_token, project.id, { title: title.trim(), due_date: dueDate || null }),
    onSuccess: () => {
      setTitle('');
      setDueDate('');
      invalidate();
    },
    onError: (err) => setError(err.message),
  });
  const patch = useMutation({
    mutationFn: ({ milestone, payload }: { milestone: Milestone; payload: Partial<Pick<Milestone, 'title' | 'status' | 'due_date'>> }) =>
      api.patchMilestone(session.csrf_token, project.id, milestone.id, payload),
    onSuccess: invalidate,
    onError: (err) => setError(err.message),
  });
  const remove = useMutation({
    mutationFn: (milestone: Milestone) => api.deleteMilestone(session.csrf_token, project.id, milestone.id),
    onSuccess: invalidate,
    onError: (err) => setError(err.message),
  });

  const pending = (milestones.data ?? []).filter((milestone) => milestone.status !== 'done' && milestone.status !== 'cancelled').length;

  return (
    <section className="linked-items project-linked-items">
      <h2>里程碑</h2>
      {project.progress_mode === 'milestone' && <p className="hint">该项目进度按里程碑完成比例自动计算。</p>}
      {milestones.isLoading && <p className="hint">加载中…</p>}
      {milestones.isError && <p className="error-line">{milestones.error.message}</p>}
      {milestones.data?.length === 0 && <p className="empty">暂无里程碑</p>}
      {(milestones.data ?? []).map((milestone) => (
        <article className="project-linked-row" key={milestone.id}>
          <label className="toggle-line compact">
            <input
              type="checkbox"
              checked={milestone.status === 'done'}
              disabled={patch.isPending}
              onChange={(event) =>
                patch.mutate({ milestone, payload: { status: event.target.checked ? 'done' : 'pending' } })
              }
            />
          </label>
          <div className="row-main">
            <strong className={milestone.status === 'done' ? 'done-text' : undefined}>{milestone.title}</strong>
            <span>{milestone.due_date ? `截止 ${milestone.due_date}` : '无截止日期'}</span>
          </div>
          <button
            className="ghost sm danger-text"
            type="button"
            title="删除里程碑"
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm(`删除里程碑「${milestone.title}」？`)) remove.mutate(milestone);
            }}
          >
            <Trash2 size={14} />
          </button>
        </article>
      ))}
      <div className="person-form">
        <input placeholder="里程碑标题（必填）" value={title} onChange={(event) => setTitle(event.target.value)} />
        <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
        <button
          className="primary"
          type="button"
          disabled={!title.trim() || create.isPending}
          onClick={() => create.mutate()}
        >
          <Plus size={16} /> 添加
        </button>
      </div>
      {pending > 0 && <p className="hint">未完成 {pending} 个</p>}
      {error && <p className="error-line">{error}</p>}
    </section>
  );
}
