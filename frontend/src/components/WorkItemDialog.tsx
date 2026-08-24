import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, Tag as TagIcon, X } from 'lucide-react';
import { FormEvent, useRef, useState } from 'react';
import { api, ItemStatus, Priority, Project, Session } from '../api/client';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { ReminderOffsetSelect } from './ReminderOffsetSelect';
import { ReminderPreviewHint } from './ReminderPreviewHint';
import { EstimatedDurationSelect } from './EstimatedDurationSelect';
import { QuarterTimePicker } from './QuarterTimePicker';
import { TagPicker } from './TagPicker';
import { WorkDraft, emptyWorkDraft, hasDraftSchedule } from '../lib/drafts';
import { priorityLabels, statusLabels } from '../lib/labels';
import { applyDueDate, applyDueTime, applyEstimatedMinutes, applyStartDate, applyStartTime } from '../lib/workSchedule';

export function WorkItemDialog({
  projects,
  session,
  timezone,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  projects: Project[];
  session: Session;
  timezone: string;
  saving: boolean;
  error?: string;
  onClose: () => void;
  onSubmit: (draft: WorkDraft, tagIds: string[]) => void;
}) {
  const queryClient = useQueryClient();
  const panelRef = useRef<HTMLFormElement>(null);
  useDialogA11y(panelRef, onClose);
  const [draft, setDraft] = useState<WorkDraft>(emptyWorkDraft());
  const [tagIds, setTagIds] = useState<string[]>([]);
  const tags = useQuery({ queryKey: ['tags'], queryFn: api.tags });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.title.trim()) onSubmit(draft, tagIds);
  }

  const createTag = useMutation({
    mutationFn: (input: { name: string; parentId: string | null }) =>
      api.createTag(session.csrf_token, { name: input.name, parent_id: input.parentId ?? undefined }),
    onSuccess: (tag) => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setTagIds((previous) => [...previous, tag.id]);
    },
  });

  function toggleTag(tagId: string) {
    setTagIds((previous) => (previous.includes(tagId) ? previous.filter((id) => id !== tagId) : [...previous, tagId]));
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="work-item-dialog-title"
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
        onSubmit={submit}
      >
        <header className="panel-header">
          <div>
            <p className="eyebrow">Work Item</p>
            <h2 id="work-item-dialog-title">新增工作事项</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭">
            <X size={16} />
          </button>
        </header>
        <label>
          事项内容
          <input data-autofocus value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
        </label>
        <div className="field-grid">
          <label>
            关联项目
            <select value={draft.project_id} onChange={(event) => setDraft({ ...draft, project_id: event.target.value })}>
              <option value="">无项目</option>
              {projects.map((project) => (
                <option value={project.id} key={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            优先级
            <select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value as Priority })}>
              {Object.entries(priorityLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="field-grid">
          <label>
            开始日期
            <input type="date" value={draft.start_date || draft.due_date} onChange={(event) => setDraft(applyStartDate(draft, event.target.value))} />
          </label>
          <label>
            开始时间
            <QuarterTimePicker value={draft.start_time || draft.due_time} onChange={(value) => setDraft(applyStartTime(draft, value))} />
          </label>
        </div>
        <details className="advanced-fields">
          <summary>更多设置</summary>
          <label>
            状态
            <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as ItemStatus })}>
              {(['planned', 'in_progress', 'waiting', 'done', 'cancelled'] as ItemStatus[]).map((status) => (
                <option value={status} key={status}>
                  {statusLabels[status]}
                </option>
              ))}
            </select>
          </label>
          <div className="field-grid">
            <label>
              截止日期
              <input type="date" value={draft.due_date} onChange={(event) => setDraft(applyDueDate(draft, event.target.value))} />
            </label>
            <label>
              截止时间
              <QuarterTimePicker value={draft.due_time} onChange={(value) => setDraft(applyDueTime(draft, value))} />
            </label>
          </div>
          <label>
            备注
            <textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
          </label>
          <label>
            预计时长（可选）
            <EstimatedDurationSelect
              value={draft.estimated_minutes}
              onChange={(value) => setDraft(applyEstimatedMinutes(draft, value))}
            />
          </label>
          <label className="toggle-line">
            <input
              type="checkbox"
              checked={draft.reminder_enabled}
              disabled={!hasDraftSchedule(draft)}
              onChange={(event) => setDraft({ ...draft, reminder_enabled: event.target.checked })}
            />
            开启应用内提醒{!hasDraftSchedule(draft) ? '（先设置日期或时间）' : ''}
          </label>
          {draft.reminder_enabled && (
            <label>
              提醒时间
              <ReminderOffsetSelect value={draft.reminder_offset} onChange={(offset) => setDraft({ ...draft, reminder_offset: offset })} />
            </label>
          )}
          <ReminderPreviewHint draft={draft} kind="work" />
          <section className="tag-box">
            <div>
              <TagIcon size={16} /> 标签
            </div>
            <TagPicker
              tags={tags.data ?? []}
              selected={tagIds}
              onToggle={toggleTag}
              onCreateTag={(name, parentId) => createTag.mutate({ name, parentId })}
            />
            {createTag.isError && <p className="error-line">{createTag.error.message}</p>}
          </section>
          <p className="hint">当前候选环境只保存应用内提醒，不发送 Feishu/ntfy。默认时区：{timezone}</p>
        </details>
        {error && <p className="error-line">{error}</p>}
        <footer className="panel-actions">
          <button className="secondary" type="button" onClick={onClose}>
            取消
          </button>
          <button className="primary" type="submit" disabled={!draft.title.trim() || saving}>
            <Save size={16} /> 保存事项
          </button>
        </footer>
      </form>
    </div>
  );
}
