import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { api, Item, Scope, Session } from '../api/client';
import { AgentProposalDeck } from '../components/AgentProposalDeck';
import { ListState } from '../components/ListState';
import { PersonalItemDrawer } from '../components/PersonalItemDrawer';
import { WorkItemDrawer } from '../components/WorkItemDrawer';
import { usePatchItem, useSaveItemWithReminder } from '../hooks/useItemActions';
import { formatItemSchedule } from '../lib/dates';

/**
 * 收集箱：未判定范围（工作/个人）的事项暂存处。归位 = 选范围并转 planned。
 */
export function InboxPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.projects });
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });
  const proposals = useQuery({ queryKey: ['agent-proposals', 'pending'], queryFn: () => api.agentProposals('pending') });
  const [error, setError] = useState<string | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const allItems = useMemo(() => [...(workItems.data ?? []), ...(personalItems.data ?? [])], [workItems.data, personalItems.data]);
  const selectedItem = allItems.find((item) => item.id === selectedItemId) ?? null;

  const inboxItems = useMemo(() => {
    return allItems
      .filter((item) => item.status === 'inbox' && !item.archived_at)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [allItems]);

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ['items', 'work'] });
    queryClient.invalidateQueries({ queryKey: ['items', 'personal'] });
    queryClient.invalidateQueries({ queryKey: ['inbox-items'] });
    queryClient.invalidateQueries({ queryKey: ['calendar'] });
    queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
  }

  const patchItem = usePatchItem(session, (item) => {
    setSelectedItemId(item.id);
    invalidateAll();
  });

  const saveItem = useSaveItemWithReminder(session, (item) => {
    setSelectedItemId(item.id);
    invalidateAll();
  });

  const triage = useMutation({
    mutationFn: ({ item, scope }: { item: Item; scope: Scope }) =>
      api.patchItem(session.csrf_token, item, { scope, status: 'planned', ...(scope === 'personal' ? { project_id: null } : {}) }),
    onSuccess: invalidateAll,
    onError: (err) => setError(err.message),
  });

  const remove = useMutation({
    mutationFn: (item: Item) => api.deleteItem(session.csrf_token, item.id),
    onSuccess: invalidateAll,
    onError: (err) => setError(err.message),
  });

  return (
    <section className="page inbox-page">
      <header className="page-header">
        <div>
          <h1>收集箱</h1>
          <p>{inboxItems.length} 条待分类 · 暂存待明确范围（工作/个人）的事项</p>
        </div>
      </header>

      <AgentProposalDeck
        proposals={proposals.data ?? []}
        session={session}
        title="收集箱待确认"
        emptyText="暂无待确认提议"
        onAppliedItem={(item) => setSelectedItemId(item.id)}
      />

      {error && <p className="error-line">{error}</p>}

      <ListState
        loading={workItems.isLoading || personalItems.isLoading}
        error={workItems.isError ? workItems.error.message : personalItems.isError ? personalItems.error.message : null}
        onRetry={() => {
          workItems.refetch();
          personalItems.refetch();
        }}
      >
        {inboxItems.length === 0 ? (
          <div className="empty">
            <p>收集箱已清空</p>
            <p className="empty-hint">所有事项均已分类或归位</p>
          </div>
        ) : (
          <div className="inbox-list">
            {inboxItems.map((item) => (
              <article className="inbox-row" key={item.id}>
                <div className="inbox-row-main">
                  <strong>{item.title}</strong>
                  <span className="inbox-row-meta">
                    {formatItemSchedule(item) || '未安排时间'}
                    {item.waiting_on ? ` · ${item.waiting_on}` : ''}
                  </span>
                </div>
                <span className="inbox-row-actions">
                  <button
                    className="ghost sm"
                    type="button"
                    disabled={triage.isPending}
                    onClick={() => triage.mutate({ item, scope: 'work' })}
                  >
                    <ArrowRight size={13} /> 工作
                  </button>
                  <button
                    className="ghost sm"
                    type="button"
                    disabled={triage.isPending}
                    onClick={() => triage.mutate({ item, scope: 'personal' })}
                  >
                    <ArrowRight size={13} /> 个人
                  </button>
                  <button className="ghost sm danger-text" type="button" title="删除" disabled={remove.isPending} onClick={() => remove.mutate(item)}>
                    <Trash2 size={13} />
                  </button>
                </span>
              </article>
            ))}
          </div>
        )}
      </ListState>

      {selectedItem?.scope === 'work' && (
        <WorkItemDrawer
          item={selectedItem}
          projects={projects.data ?? []}
          session={session}
          saving={saveItem.isPending || patchItem.isPending}
          error={saveItem.error?.message ?? patchItem.error?.message}
          onClose={() => setSelectedItemId(null)}
          onSave={(draft, reminderTouched, tagIds) => saveItem.mutate({ item: selectedItem, draft, reminderTouched, tagIds })}
          onStatus={(status) => patchItem.mutate({ item: selectedItem, payload: { status } })}
          onReschedule={(payload) => patchItem.mutate({ item: selectedItem, payload })}
          onDelete={() => {
            void api.deleteItem(session.csrf_token, selectedItem.id).then(() => {
              setSelectedItemId(null);
              invalidateAll();
            });
          }}
        />
      )}
      {selectedItem?.scope === 'personal' && (
        <PersonalItemDrawer
          item={selectedItem}
          session={session}
          saving={saveItem.isPending || patchItem.isPending}
          error={saveItem.error?.message ?? patchItem.error?.message}
          onClose={() => setSelectedItemId(null)}
          onSave={(draft, reminderTouched, tagIds) => saveItem.mutate({ item: selectedItem, draft, reminderTouched, tagIds })}
          onStatus={(status) => patchItem.mutate({ item: selectedItem, payload: { status } })}
          onReschedule={(payload) => patchItem.mutate({ item: selectedItem, payload })}
          onDelete={() => {
            void api.deleteItem(session.csrf_token, selectedItem.id).then(() => {
              setSelectedItemId(null);
              invalidateAll();
            });
          }}
        />
      )}
    </section>
  );
}
