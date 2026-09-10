import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CalendarDays, Clock, Hourglass, Plus, Repeat, TriangleAlert, User, Users, X } from 'lucide-react';
import { FormEvent, KeyboardEvent, ReactNode, useMemo, useRef, useState } from 'react';
import { api, Item, Scope, Session } from '../api/client';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { buildPersonalPayload, buildWorkPayload, emptyPersonalDraft, emptyWorkDraft } from '../lib/drafts';
import { resolveScope } from '../lib/quickAdd';
import { parseQuickAdd } from '../lib/quickAdd';
import { formatDuration, scopeLabel } from '../lib/labels';
import { choiceToRecurrenceFields, recurrenceOptions } from '../lib/recurrence';
import { normalizeCreateDraft, reminderTiming } from '../lib/workSchedule';

export function QuickAddDialog({
  session,
  defaultScope,
  onClose,
  onCreated,
}: {
  session: Session;
  defaultScope: Scope;
  onClose: () => void;
  onCreated?: (item: Item) => void;
}) {
  const queryClient = useQueryClient();
  const panelRef = useRef<HTMLFormElement>(null);
  useDialogA11y(panelRef, onClose);
  const [input, setInput] = useState('');
  const parsed = useMemo(() => parseQuickAdd(input), [input]);
  const prefs = useQuery({ queryKey: ['preferences'], queryFn: api.preferences });
  const directory = useQuery({ queryKey: ['people'], queryFn: () => api.people(true) });
  const resolution = useMemo(
    () => resolveScope(parsed, prefs.data?.identity_scope_rules ?? [], directory.data ?? []),
    [parsed, prefs.data, directory.data],
  );
  const toInbox = resolution.source === 'inbox';
  const scope: Scope = resolution.scope ?? defaultScope;
  const previewDraft = useMemo(
    () =>
      normalizeCreateDraft({
        ...(scope === 'work' ? emptyWorkDraft() : emptyPersonalDraft()),
        title: parsed.title,
        start_date: parsed.start_date,
        start_time: parsed.start_time,
        estimated_minutes: parsed.estimated_minutes ? String(parsed.estimated_minutes) : '',
        waiting_on: parsed.waiting_on,
        ...choiceToRecurrenceFields(parsed.recurrence),
        ...(parsed.status === 'waiting' ? { status: 'waiting' as const } : {}),
      }),
    [parsed, scope],
  );

  const create = useMutation({
    mutationFn: async (mode: 'close' | 'continue') => {
      const payload = scope === 'work' ? buildWorkPayload(previewDraft as ReturnType<typeof emptyWorkDraft>) : buildPersonalPayload(previewDraft);
      payload.intake_text = input.trim();
      payload.intake_scope_source = resolution.source;
      payload.intake_origin = 'web';
      payload.intake_normalization = 'none';
      if (toInbox) payload.status = 'inbox';
      if (parsed.waiting_on && parsed.person_role) {
        const people = directory.data ?? (await api.people(true));
        const existing = people.find((person) => person.name.trim() === parsed.waiting_on.trim());
        const person = existing ?? (await api.createPerson(session.csrf_token, { name: parsed.waiting_on.trim(), identity: null }));
        payload.people = [{ person_id: person.id, role: parsed.person_role }];
      }
      const item = await api.createItem(session.csrf_token, payload);
      if (parsed.reminder_offset !== null && (previewDraft.start_date || previewDraft.due_date)) {
        await api.putReminder(session.csrf_token, item.id, {
          timing: reminderTiming(previewDraft),
          offset_minutes: parsed.reminder_offset,
          timezone: session.timezone,
          external_enabled: false,
        });
      }
      return { item, mode };
    },
    onSuccess: ({ item, mode }) => {
      queryClient.invalidateQueries({ queryKey: ['items', item.scope] });
      queryClient.invalidateQueries({ queryKey: ['inbox-items'] });
      queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
      queryClient.invalidateQueries({ queryKey: ['reminder-deliveries'] });
      onCreated?.(item);
      if (mode === 'continue') {
        setInput('');
      } else {
        onClose();
      }
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (parsed.title && !create.isPending) create.mutate('close');
  }

  function onFormKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      if (parsed.title && !create.isPending) create.mutate('continue');
    }
  }

  const hasInput = input.trim().length > 0;

  // 时间段冲突检测: 与当天两个范围内带开始时间的事项比对(对方时长缺失按 60 分钟计, 非阻塞提醒)
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });
  const conflicts = useMemo(() => {
    if (!previewDraft.start_date || !previewDraft.start_time) return [] as Array<{ item: Item; startMin: number; endMin: number }>;
    const [h, m] = previewDraft.start_time.split(':').map(Number);
    const startMin = h * 60 + m;
    const endMin = startMin + (Number(previewDraft.estimated_minutes) || 60);
    const found: Array<{ item: Item; startMin: number; endMin: number }> = [];
    for (const item of [...(workItems.data ?? []), ...(personalItems.data ?? [])]) {
      if (!item.start_at || item.all_day) continue;
      if (item.status === 'done' || item.status === 'cancelled' || item.status === 'waiting') continue;
      const at = new Date(item.start_at);
      const dateKey = `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, '0')}-${String(at.getDate()).padStart(2, '0')}`;
      if (dateKey !== previewDraft.start_date) continue;
      const otherStart = at.getHours() * 60 + at.getMinutes();
      const otherEnd = otherStart + (item.estimated_minutes ?? 60);
      if (startMin < otherEnd && otherStart < endMin) found.push({ item, startMin: otherStart, endMin: otherEnd });
    }
    return found.sort((a, b) => a.startMin - b.startMin);
  }, [previewDraft, workItems.data, personalItems.data]);

  function fmtMin(min: number) {
    return `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="modal-panel quick-add-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="quick-add-title"
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
        onSubmit={submit}
        onKeyDown={onFormKeyDown}
      >
        <header className="panel-header">
          <h2 id="quick-add-title">新建事项</h2>
          <button className="icon-button" type="button" onClick={onClose} title="关闭 (Esc)">
            <X size={16} />
          </button>
        </header>

        <input
          className="quick-add-input"
          data-autofocus
          placeholder="例如：明天下午3点 约牙医 预计1小时 提前1小时提醒 #个人"
          value={input}
          onChange={(event) => setInput(event.target.value)}
        />

        {hasInput && (
          <div className="quick-add-preview-card" aria-live="polite">
            {parsed.title ? (
              <p className="preview-title">{parsed.title}</p>
            ) : (
              <p className="preview-title empty">未识别到标题</p>
            )}
            <div className="preview-fields">
              <PreviewField
                icon={<User size={13} />}
                label={toInbox ? '范围：待分类（收集箱）' : `范围：${scopeLabel(scope)}${resolution.source === 'identity' ? '（按协作者身份）' : ''}`}
              />
              {previewDraft.start_date && (
                <PreviewField
                  icon={<CalendarDays size={13} />}
                  label={`时间：${previewDraft.start_date}${previewDraft.start_time ? ` ${previewDraft.start_time}` : ''}`}
                />
              )}
              {previewDraft.due_date && (
                <PreviewField icon={<CalendarDays size={13} />} label={`截止：${previewDraft.due_date}${previewDraft.due_time ? ` ${previewDraft.due_time}` : ''}`} />
              )}
              {previewDraft.estimated_minutes && <PreviewField icon={<Hourglass size={13} />} label={`时长：${formatDuration(Number(previewDraft.estimated_minutes))}`} />}
              {parsed.reminder_offset !== null && <PreviewField icon={<Bell size={13} />} label={`提醒：提前 ${formatDuration(parsed.reminder_offset)}`} />}
              {parsed.recurrence && (
                <PreviewField icon={<Repeat size={13} />} label={`重复：${recurrenceOptions.find((option) => option.value === parsed.recurrence)?.label ?? ''}`} />
              )}
              {parsed.waiting_on && (
                <PreviewField
                  icon={<Users size={13} />}
                  label={`${parsed.person_role === 'together' ? '协作' : '等待'}：${parsed.waiting_on}`}
                />
              )}
              {parsed.status === 'waiting' && !parsed.waiting_on && <PreviewField icon={<Clock size={13} />} label="状态：等待他人" />}
            </div>
            {conflicts.length > 0 && (
              <p className="preview-conflict">
                <TriangleAlert size={13} /> 与 {fmtMin(conflicts[0].startMin)}–{fmtMin(conflicts[0].endMin)}「{conflicts[0].item.title}」时间重叠
                {conflicts.length > 1 ? `，另与 ${conflicts.length - 1} 项重叠` : ''}
              </p>
            )}
          </div>
        )}

        <details className="quick-add-syntax">
          <summary>语法帮助</summary>
          <div className="syntax-grid">
            <span>
              <strong>时间</strong>：今天 / 明天 / 后天 / 周三、下午3点 / 15:00
            </span>
            <span>
              <strong>时长</strong>：~30 / ~1.5h（有时间未写时长时默认 1 小时）
            </span>
            <span>
              <strong>提醒</strong>：提前30分钟 / 提前1小时提醒
            </span>
            <span>
              <strong>重复</strong>：每天 / 每周重复
            </span>
            <span>
              <strong>协作</strong>：@人名（或「和人名一起」）
            </span>
            <span>
              <strong>等待</strong>：!人名（或「等人名」）
            </span>
            <span>
              <strong>范围</strong>：#工作 / #个人
            </span>
          </div>
        </details>

        {create.isError && <p className="error-line">{create.error.message}</p>}

        <footer className="panel-actions">
          <button className="ghost" type="button" onClick={onClose}>
            取消
          </button>
          <button className="secondary" type="button" disabled={!parsed.title || create.isPending} onClick={() => create.mutate('continue')}>
            创建并继续 <kbd>⌘↵</kbd>
          </button>
          <button className="primary" type="submit" disabled={!parsed.title || create.isPending}>
            <Plus size={16} /> {toInbox ? '收入收集箱' : `创建事项${scope === defaultScope ? '' : `（到${scopeLabel(scope)}）`}`}
          </button>
        </footer>
        <p className="quick-add-keys">
          <kbd>Enter</kbd> 创建并关闭 · <kbd>⌘ Enter</kbd> 创建并继续 · <kbd>Esc</kbd> 关闭
        </p>
      </form>
    </div>
  );
}

function PreviewField({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="preview-field">
      {icon}
      {label}
    </span>
  );
}
