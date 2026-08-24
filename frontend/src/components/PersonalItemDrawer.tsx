import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, Save, Tag as TagIcon, X } from 'lucide-react';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { api, Item, ItemStatus, Session } from '../api/client';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { PersonalDraft, hasPersonalDraftSchedule, personalDraftFromItem } from '../lib/drafts';
import { FocusControls } from './FocusControls';
import { buildReschedulePatch, rescheduleOptions } from '../lib/reschedule';
import { applyDueDate, applyDueTime, applyEstimatedMinutes, applyStartDate, applyStartTime } from '../lib/workSchedule';
import { RecurrenceFields } from './RecurrenceFields';
import { ReminderOffsetSelect } from './ReminderOffsetSelect';
import { ReminderPreviewHint } from './ReminderPreviewHint';
import { EstimatedDurationSelect } from './EstimatedDurationSelect';
import { QuarterTimePicker } from './QuarterTimePicker';
import { PersonPicker } from './PersonPicker';
import { TagPicker } from './TagPicker';

export function PersonalItemDrawer({
  item,
  session,
  saving,
  error,
  onClose,
  onSave,
  onStatus,
  onReschedule,
  onDelete,
}: {
  item: Item;
  session: Session;
  saving: boolean;
  error?: string;
  onClose: () => void;
  onSave: (draft: PersonalDraft, reminderTouched: boolean, tagIds: string[] | null) => void;
  onStatus: (status: ItemStatus) => void;
  onReschedule: (payload: Partial<Item>) => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();
  const drawerRef = useRef<HTMLElement>(null);
  useDialogA11y(drawerRef, onClose);
  const [draft, setDraft] = useState<PersonalDraft>(() => personalDraftFromItem(item));
  const [reminderTouched, setReminderTouched] = useState(false);
  const [tagIds, setTagIds] = useState<string[] | null>(null);
  const reminder = useQuery({ queryKey: ['item-reminder', item.id], queryFn: () => api.getReminder(item.id) });
  const tags = useQuery({ queryKey: ['tags'], queryFn: api.tags });
  const channels = useQuery({ queryKey: ['reminder-channels'], queryFn: api.reminderChannels });
  const externalConfigured = Boolean(channels.data?.feishu_configured || channels.data?.ntfy_configured);

  useEffect(() => {
    setDraft(personalDraftFromItem(item));
    setReminderTouched(false);
    setTagIds(null);
  }, [item]);

  useEffect(() => {
    const currentReminder = reminder.data;
    if (reminderTouched || !currentReminder) return;
    setDraft((current) => ({
      ...current,
      reminder_enabled: true,
      reminder_offset: currentReminder.offset_minutes,
      reminder_external: currentReminder.external_enabled,
    }));
  }, [reminder.data, reminderTouched]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.title.trim()) onSave(draft, reminderTouched, tagIds);
  }

  const createTag = useMutation({
    mutationFn: (input: { name: string; parentId: string | null }) =>
      api.createTag(session.csrf_token, { name: input.name, parent_id: input.parentId ?? undefined }),
    onSuccess: (tag) => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setTagIds((previous) => [...(previous ?? item.tags.map((existing) => existing.id)), tag.id]);
    },
  });

  function toggleTag(tagId: string) {
    setTagIds((previous) => {
      const base = previous ?? item.tags.map((existing) => existing.id);
      return base.includes(tagId) ? base.filter((id) => id !== tagId) : [...base, tagId];
    });
  }

  return (
    <aside className="detail-drawer personal-drawer" role="dialog" aria-modal="true" aria-labelledby="personal-drawer-title" ref={drawerRef}>
      <form onSubmit={submit}>
        <header className="panel-header">
          <div>
            <p className="eyebrow">Personal Item</p>
            <h2 id="personal-drawer-title">个人事项</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭">
            <X size={16} />
          </button>
        </header>
        <label>
          事项标题
          <input data-autofocus value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
        </label>
        <div className="field-grid">
          <label>
            开始日期
            <input type="date" value={draft.start_date} onChange={(event) => setDraft(applyStartDate(draft, event.target.value))} />
          </label>
          <label>
            开始时间
            <QuarterTimePicker value={draft.start_time} onChange={(value) => setDraft(applyStartTime(draft, value))} />
          </label>
        </div>
        <label>
          预计时长
          <EstimatedDurationSelect
            value={draft.estimated_minutes}
            onChange={(value) => setDraft(applyEstimatedMinutes(draft, value))}
          />
        </label>
        <PersonPicker session={session} value={draft.people} onChange={(people) => setDraft({ ...draft, people })} />
        <details className="advanced-fields">
          <summary>截止日期（可选）</summary>
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
        </details>
        <RecurrenceFields value={draft} onChange={(patch) => setDraft((current) => ({ ...current, ...patch }))} />
        <div className="reschedule-chips" aria-label="快捷改期">
          {rescheduleOptions.map((option) => (
            <button
              className="chip"
              type="button"
              key={option.value}
              disabled={saving}
              onClick={() => onReschedule(buildReschedulePatch(option.value))}
            >
              {option.label}
            </button>
          ))}
        </div>
        <section className="reminder-box">
          <div>
            <Bell size={16} /> 应用内提醒
          </div>
          <label className="toggle-line">
            <input
              type="checkbox"
              checked={draft.reminder_enabled}
              disabled={!hasPersonalDraftSchedule(draft)}
              onChange={(event) => {
                setReminderTouched(true);
                setDraft({ ...draft, reminder_enabled: event.target.checked });
              }}
            />
            {hasPersonalDraftSchedule(draft) ? '保存时更新提醒' : '先设置开始或截止时间'}
          </label>
          {draft.reminder_enabled && (
            <ReminderOffsetSelect
              value={draft.reminder_offset}
              onChange={(offset) => {
                setReminderTouched(true);
                setDraft({ ...draft, reminder_offset: offset });
              }}
            />
          )}
          {draft.reminder_enabled && (
            <label className="toggle-line">
              <input
                type="checkbox"
                checked={draft.reminder_external}
                disabled={!externalConfigured}
                onChange={(event) => {
                  setReminderTouched(true);
                  setDraft({ ...draft, reminder_external: event.target.checked });
                }}
              />
              同时发送外部通知（飞书 / ntfy）
            </label>
          )}
          {draft.reminder_enabled && !externalConfigured && (
            <p className="hint">外部通知未配置：需在服务器环境变量设置飞书 webhook 或 ntfy topic。</p>
          )}
          <ReminderPreviewHint draft={draft} kind="personal" />
        </section>
        <label>
          备注
          <textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
        </label>
        <section className="tag-box">
          <div>
            <TagIcon size={16} /> 标签
          </div>
          <TagPicker
            tags={tags.data ?? []}
            selected={tagIds ?? item.tags.map((existing) => existing.id)}
            onToggle={toggleTag}
            onCreateTag={(name, parentId) => createTag.mutate({ name, parentId })}
          />
          {createTag.isError && <p className="error-line">{createTag.error.message}</p>}
        </section>
        {error && <p className="error-line">{error}</p>}
        <FocusControls itemId={item.id} session={session} />
        <footer className="panel-actions split">
          <button className="secondary" type="button" onClick={() => onStatus(item.status === 'done' ? 'planned' : 'done')}>
            {item.status === 'done' ? '重新打开' : '标记完成'}
          </button>
          <button className="danger" type="button" onClick={() => onStatus('cancelled')} disabled={item.status === 'cancelled'}>
            取消事项
          </button>
          <button className="danger" type="button" onClick={onDelete} title="移入回收站（可在设置页恢复）">
            删除
          </button>
          <button className="primary" type="submit" disabled={!draft.title.trim() || saving}>
            <Save size={16} /> 保存
          </button>
        </footer>
      </form>
    </aside>
  );
}
