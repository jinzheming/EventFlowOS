import { useQuery } from '@tanstack/react-query';
import { Link2, X } from 'lucide-react';
import { useState } from 'react';
import { api, type Item, type Scope } from '../api/client';
import { formatItemSchedule } from '../lib/dates';
import { statusLabels } from '../lib/labels';

type RelationValues = Pick<Item, 'predecessor_item_ids' | 'successor_item_ids'>;

export function ItemRelationsField({
  scope,
  projectId,
  itemId,
  value,
  onChange,
}: {
  scope: Scope;
  projectId: string | null;
  itemId?: string;
  value: RelationValues;
  onChange: (patch: Partial<RelationValues>) => void;
}) {
  const [predecessorChoice, setPredecessorChoice] = useState('');
  const [successorChoice, setSuccessorChoice] = useState('');
  const items = useQuery({
    queryKey: ['project-items', scope, projectId],
    queryFn: () => api.projectItems(scope, projectId, true),
  });
  const candidates = (items.data ?? []).filter((candidate) =>
    candidate.id !== itemId && candidate.scope === scope && candidate.project_id === projectId && !candidate.deleted_at,
  );
  const byId = new Map(candidates.map((candidate) => [candidate.id, candidate]));
  const predecessors = value.predecessor_item_ids ?? [];
  const successors = value.successor_item_ids ?? [];

  function add(which: 'predecessor' | 'successor') {
    const selected = which === 'predecessor' ? predecessorChoice : successorChoice;
    if (!selected) return;
    if (which === 'predecessor') {
      onChange({ predecessor_item_ids: predecessors.includes(selected) ? predecessors : [...predecessors, selected] });
      setPredecessorChoice('');
    } else {
      onChange({ successor_item_ids: successors.includes(selected) ? successors : [...successors, selected] });
      setSuccessorChoice('');
    }
  }

  function remove(which: 'predecessor' | 'successor', id: string) {
    if (which === 'predecessor') onChange({ predecessor_item_ids: predecessors.filter((value) => value !== id) });
    else onChange({ successor_item_ids: successors.filter((value) => value !== id) });
  }

  return (
    <section className="tag-box item-relations-box">
      <div><Link2 size={16} /> 事项关系</div>
      <p className="hint">可添加多个同范围、同项目归属的事项。前置事项需先完成，后续事项由本事项推动。</p>
      {(['predecessor', 'successor'] as const).map((which) => {
        const selected = which === 'predecessor' ? predecessors : successors;
        const choice = which === 'predecessor' ? predecessorChoice : successorChoice;
        const setChoice = which === 'predecessor' ? setPredecessorChoice : setSuccessorChoice;
        const selectedLabel = which === 'predecessor' ? '前置事项' : '后续事项';
        const excluded = new Set([...predecessors, ...successors]);
        return (
          <div className="relation-group" key={which}>
            <strong>{selectedLabel}</strong>
            <div className="relation-chips">
              {selected.map((id) => {
                const related = byId.get(id);
                return (
                  <span className="relation-chip" key={id}>
                    <span>{related?.title ?? `事项 ${id.slice(0, 8)}`}{related && <small>{statusLabels[related.status]} · {formatItemSchedule(related)}</small>}</span>
                    <button type="button" className="icon-button" title={`移除${selectedLabel}`} aria-label={`移除${selectedLabel}`} onClick={() => remove(which, id)}><X size={14} /></button>
                  </span>
                );
              })}
              {!selected.length && <span className="hint">暂无</span>}
            </div>
            <div className="field-grid relation-add-row">
              <select value={choice} onChange={(event) => setChoice(event.target.value)} aria-label={`选择${selectedLabel}`}>
                <option value="">选择事项</option>
                {candidates.filter((candidate) => !candidate.archived_at && !excluded.has(candidate.id)).map((candidate) => (
                  <option value={candidate.id} key={candidate.id}>
                    {candidate.title} · {statusLabels[candidate.status]} · {formatItemSchedule(candidate)}
                  </option>
                ))}
              </select>
              <button className="secondary" type="button" disabled={!choice} onClick={() => add(which)}>添加</button>
            </div>
          </div>
        );
      })}
      {items.isLoading && <p className="hint">正在加载同项目事项…</p>}
      {items.isError && <p className="error-line">无法加载候选事项：{items.error.message}</p>}
    </section>
  );
}
