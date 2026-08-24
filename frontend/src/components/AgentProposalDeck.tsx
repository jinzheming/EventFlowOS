import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, EyeOff, Pencil, ShieldAlert, XCircle } from 'lucide-react';
import { FormEvent, useMemo, useState } from 'react';
import { AgentProposal, api, Item, ItemStatus, Priority, Scope, Session } from '../api/client';

interface AgentProposalDeckProps {
  proposals: AgentProposal[];
  session: Session;
  title?: string;
  emptyText?: string;
  compact?: boolean;
  onAppliedItem?: (item: Item) => void;
}

interface EditableProposalDraft {
  title: string;
  scope: Scope;
  status: ItemStatus;
  priority: Priority;
  all_day: boolean;
  start_at: string;
  due_at: string;
  start_date: string;
  due_date: string;
  estimated_minutes: string;
  notes: string;
}

type ProposalAction =
  | { type: 'approve'; proposal: AgentProposal }
  | { type: 'approve_edit'; proposal: AgentProposal; draft: EditableProposalDraft }
  | { type: 'reject'; proposal: AgentProposal }
  | { type: 'ignore'; proposal: AgentProposal };

const sourceLabels: Record<string, string> = {
  agent: 'Agent',
  feishu_im: '飞书 IM',
  tencent_meeting: '腾讯会议',
};

const riskLabels: Record<string, string> = {
  l1: 'L1 低风险',
  l2: 'L2 待确认',
  l3: 'L3 高风险',
};

export function AgentProposalDeck({ proposals, session, title = '待确认提议', emptyText, compact = false, onAppliedItem }: AgentProposalDeckProps) {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditableProposalDraft | null>(null);
  const sorted = useMemo(() => proposals.slice().sort(compareProposals), [proposals]);

  const action = useMutation({
    mutationFn: async (input: ProposalAction) => {
      if (input.type === 'approve') {
        return api.approveProposal(session.csrf_token, input.proposal.id);
      }
      if (input.type === 'approve_edit') {
        return api.approveProposal(session.csrf_token, input.proposal.id, { edited_payload: editablePayload(input.proposal, input.draft) });
      }
      if (input.type === 'reject') {
        await api.rejectProposal(session.csrf_token, input.proposal.id, 'Rejected from approval queue.');
        return { proposal: input.proposal, item: null };
      }
      await api.ignoreProposal(session.csrf_token, input.proposal.id, 'Ignored from approval queue.');
      return { proposal: input.proposal, item: null };
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['agent-proposals'] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
      queryClient.invalidateQueries({ queryKey: ['reminder-deliveries'] });
      if (result.item) onAppliedItem?.(result.item);
      setEditingId(null);
      setDraft(null);
    },
  });

  if (sorted.length === 0) {
    return emptyText ? <p className="empty agent-proposal-empty">{emptyText}</p> : null;
  }

  return (
    <section className={compact ? 'agent-proposal-deck compact' : 'agent-proposal-deck'} aria-label={title}>
      <header className="agent-proposal-header">
        <div>
          <p className="eyebrow">Agent Handoff</p>
          <h2>{title}</h2>
        </div>
        <span>{sorted.length}</span>
      </header>
      {sorted.map((proposal) => {
        const isEditing = editingId === proposal.id && draft;
        const missingFields = asStringArray(proposal.evidence.missing_fields);
        const meeting = meetingMeta(proposal);
        return (
          <article className={`agent-proposal-card risk-${proposal.risk_tier}`} key={proposal.id}>
            <div className="agent-proposal-main">
              <span className="agent-proposal-risk">
                <ShieldAlert size={14} /> {riskLabels[proposal.risk_tier] ?? proposal.risk_tier.toUpperCase()}
              </span>
              <div>
                <h3>{stringValue(proposal.proposed_payload.title) || '未命名事项'}</h3>
                <p>{scheduleSummary(proposal.proposed_payload) || '未安排时间'} · {sourceLabels[proposal.source_type] ?? proposal.source_type}</p>
              </div>
              <span className="agent-proposal-confidence">{formatConfidence(proposal.confidence)}</span>
            </div>
            {proposal.reason && <p className="agent-proposal-reason">{proposal.reason}</p>}
            {meeting && (
              <div className="agent-proposal-meeting">
                {meeting.joinUrl && <a href={meeting.joinUrl} target="_blank" rel="noreferrer">入会链接</a>}
                {meeting.meetingId && <span>会议号 {meeting.meetingId}</span>}
                {meeting.meetingCode && <span>密码 {meeting.meetingCode}</span>}
              </div>
            )}
            {missingFields.length > 0 && <p className="agent-proposal-missing">缺失字段：{missingFields.join('、')}</p>}
            <details className="agent-proposal-evidence">
              <summary>查看证据</summary>
              <pre>{JSON.stringify(proposal.evidence, null, 2)}</pre>
            </details>

            {isEditing && (
              <form
                className="agent-proposal-edit"
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  if (draft.title.trim()) action.mutate({ type: 'approve_edit', proposal, draft });
                }}
              >
                <label>
                  标题
                  <input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
                </label>
                <div className="field-grid">
                  <label>
                    范围
                    <select value={draft.scope} onChange={(event) => setDraft({ ...draft, scope: event.target.value as Scope })}>
                      <option value="work">工作</option>
                      <option value="personal">个人</option>
                    </select>
                  </label>
                  <label>
                    状态
                    <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as ItemStatus })}>
                      {(['inbox', 'planned', 'in_progress', 'waiting'] as ItemStatus[]).map((status) => <option value={status} key={status}>{status}</option>)}
                    </select>
                  </label>
                  <label>
                    优先级
                    <select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value as Priority })}>
                      {(['low', 'normal', 'high', 'urgent'] as Priority[]).map((priority) => <option value={priority} key={priority}>{priority}</option>)}
                    </select>
                  </label>
                  <label className="toggle-line">
                    <input type="checkbox" checked={draft.all_day} onChange={(event) => setDraft({ ...draft, all_day: event.target.checked })} />
                    全天事项
                  </label>
                </div>
                <div className="field-grid">
                  <label>
                    开始时间
                    <input value={draft.start_at} placeholder="2026-08-24T10:00:00+08:00" onChange={(event) => setDraft({ ...draft, start_at: event.target.value })} />
                  </label>
                  <label>
                    结束时间
                    <input value={draft.due_at} placeholder="2026-08-24T10:30:00+08:00" onChange={(event) => setDraft({ ...draft, due_at: event.target.value })} />
                  </label>
                </div>
                <div className="field-grid">
                  <label>
                    开始日期
                    <input type="date" value={draft.start_date} onChange={(event) => setDraft({ ...draft, start_date: event.target.value })} />
                  </label>
                  <label>
                    截止日期
                    <input type="date" value={draft.due_date} onChange={(event) => setDraft({ ...draft, due_date: event.target.value })} />
                  </label>
                  <label>
                    预计分钟
                    <input inputMode="numeric" value={draft.estimated_minutes} onChange={(event) => setDraft({ ...draft, estimated_minutes: event.target.value })} />
                  </label>
                </div>
                <label>
                  备注
                  <textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
                </label>
                <div className="panel-actions">
                  <button className="primary" type="submit" disabled={!draft.title.trim() || action.isPending}>
                    <Check size={14} /> 修改后确认
                  </button>
                  <button className="ghost" type="button" onClick={() => { setEditingId(null); setDraft(null); }}>
                    取消修改
                  </button>
                </div>
              </form>
            )}

            {!isEditing && (
              <footer className="agent-proposal-actions">
                <button className="primary sm" type="button" disabled={action.isPending} onClick={() => action.mutate({ type: 'approve', proposal })}>
                  <Check size={14} /> 确认
                </button>
                <button className="ghost sm" type="button" disabled={action.isPending} onClick={() => { setEditingId(proposal.id); setDraft(draftFromProposal(proposal)); }}>
                  <Pencil size={14} /> 修改后确认
                </button>
                <button className="ghost sm danger-text" type="button" disabled={action.isPending} onClick={() => action.mutate({ type: 'reject', proposal })}>
                  <XCircle size={14} /> 拒绝
                </button>
                <button className="ghost sm" type="button" disabled={action.isPending} onClick={() => action.mutate({ type: 'ignore', proposal })}>
                  <EyeOff size={14} /> 忽略
                </button>
              </footer>
            )}
          </article>
        );
      })}
      {action.isError && <p className="error-line">{action.error.message}</p>}
    </section>
  );
}

function compareProposals(a: AgentProposal, b: AgentProposal) {
  const riskRank = { l3: 0, l2: 1, l1: 2 } as Record<string, number>;
  return (riskRank[a.risk_tier] ?? 3) - (riskRank[b.risk_tier] ?? 3) || b.created_at.localeCompare(a.created_at);
}

function draftFromProposal(proposal: AgentProposal): EditableProposalDraft {
  const payload = proposal.proposed_payload;
  return {
    title: stringValue(payload.title) || '',
    scope: (stringValue(payload.scope) as Scope) || 'work',
    status: (stringValue(payload.status) as ItemStatus) || 'planned',
    priority: (stringValue(payload.priority) as Priority) || 'normal',
    all_day: booleanValue(payload.all_day, true),
    start_at: stringValue(payload.start_at) || '',
    due_at: stringValue(payload.due_at) || '',
    start_date: stringValue(payload.start_date) || '',
    due_date: stringValue(payload.due_date) || '',
    estimated_minutes: numberString(payload.estimated_minutes),
    notes: stringValue(payload.notes) || '',
  };
}

function editablePayload(proposal: AgentProposal, draft: EditableProposalDraft): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    title: draft.title.trim(),
    scope: draft.scope,
    status: draft.status,
    priority: draft.priority,
    all_day: draft.all_day,
    start_at: draft.start_at.trim() || null,
    due_at: draft.due_at.trim() || null,
    start_date: draft.start_date || null,
    due_date: draft.due_date || null,
    estimated_minutes: draft.estimated_minutes.trim() ? Number(draft.estimated_minutes) : null,
    notes: draft.notes.trim() || null,
  };
  if (typeof proposal.proposed_payload.expected_version === 'number') {
    payload.expected_version = proposal.proposed_payload.expected_version;
  }
  return payload;
}

function scheduleSummary(payload: Record<string, unknown>) {
  const start = stringValue(payload.start_at) || stringValue(payload.start_date);
  const due = stringValue(payload.due_at) || stringValue(payload.due_date);
  if (start && due) return `${start} → ${due}`;
  return start || due || '';
}

function meetingMeta(proposal: AgentProposal) {
  const joinUrl = stringValue(proposal.evidence.join_url) || stringValue(proposal.proposed_payload.join_url);
  const meetingId = stringValue(proposal.evidence.meeting_id) || stringValue(proposal.proposed_payload.meeting_id);
  const meetingCode = stringValue(proposal.evidence.meeting_code) || stringValue(proposal.proposed_payload.meeting_code);
  if (!joinUrl && !meetingId && !meetingCode) return null;
  return { joinUrl, meetingId, meetingCode };
}

function formatConfidence(value: number | null) {
  if (value === null) return '置信度 -';
  return `置信度 ${Math.round(value * 100)}%`;
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value : value === null || value === undefined ? '' : String(value);
}

function booleanValue(value: unknown, fallback: boolean) {
  return typeof value === 'boolean' ? value : fallback;
}

function numberString(value: unknown) {
  return typeof value === 'number' ? String(value) : typeof value === 'string' ? value : '';
}

function asStringArray(value: unknown) {
  return Array.isArray(value) ? value.map((entry) => String(entry)).filter(Boolean) : [];
}
