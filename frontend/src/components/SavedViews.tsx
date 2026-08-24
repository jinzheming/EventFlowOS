import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BookmarkPlus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, SavedViewSpec, Session } from '../api/client';
import type { ItemQuickFilter } from '../lib/itemFilters';

const HANDOFF_KEY = 'pa-apply-view';

export function stashViewHandoff(spec: SavedViewSpec) {
  sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(spec));
}

/** Page mount: consume a stashed saved-view spec and apply it. */
export function useApplyViewHandoff(
  page: 'work' | 'personal',
  apply: (spec: SavedViewSpec & { quickFilter: ItemQuickFilter }) => void,
) {
  useEffect(() => {
    const raw = sessionStorage.getItem(HANDOFF_KEY);
    if (!raw) return;
    sessionStorage.removeItem(HANDOFF_KEY);
    try {
      const spec = JSON.parse(raw) as SavedViewSpec;
      if (spec.page === page) apply(spec as SavedViewSpec & { quickFilter: ItemQuickFilter });
      else sessionStorage.setItem(HANDOFF_KEY, raw); // 目标页不是本页，留给目标页
    } catch {
      // 损坏的接力数据直接丢弃
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);
}

/** 「存为视图」按钮：保存当前筛选组合为侧栏智能视图。 */
export function SaveViewButton({ session, spec }: { session: Session; spec: SavedViewSpec }) {
  const queryClient = useQueryClient();
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api.createSavedView(session.csrf_token, { name: name.trim(), spec }),
    onSuccess: () => {
      setNaming(false);
      setName('');
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['saved-views'] });
    },
    onError: (err) => setError(err.message),
  });

  const isActive = spec.quickFilter !== 'all' || spec.highPriority || spec.search.trim() !== '';
  if (!isActive && !naming) return null;

  if (!naming) {
    return (
      <button className="ghost sm" type="button" title="把当前筛选存为侧栏智能视图" onClick={() => setNaming(true)}>
        <BookmarkPlus size={13} /> 存为视图
      </button>
    );
  }
  return (
    <form
      className="save-view-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) create.mutate();
      }}
    >
      <input placeholder="视图名称，如：本周高优" value={name} onChange={(event) => setName(event.target.value)} data-autofocus />
      <button className="primary" type="submit" disabled={!name.trim() || create.isPending}>
        保存
      </button>
      <button className="ghost sm" type="button" onClick={() => { setNaming(false); setError(null); }}>
        取消
      </button>
      {error && <p className="error-line">{error}</p>}
    </form>
  );
}
