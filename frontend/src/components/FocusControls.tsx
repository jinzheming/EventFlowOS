import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Circle, Play, Square } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, Item, Session } from '../api/client';
import { formatDuration } from '../lib/labels';

/** 抽屉内专注控件：本项计时中显示停止，否则显示开始。 */
export function FocusControls({ itemId, session }: { itemId: string; session: Session }) {
  const queryClient = useQueryClient();
  const active = useQuery({ queryKey: ['focus', 'active'], queryFn: api.activeFocus });
  const summary = useQuery({ queryKey: ['focus', 'summary', itemId], queryFn: () => api.focusSummary(itemId) });

  const toggle = useMutation({
    mutationFn: (running: boolean) => (running ? api.stopFocus(session.csrf_token, itemId) : api.startFocus(session.csrf_token, itemId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['focus'] });
    },
  });

  const runningHere = active.data?.item_id === itemId;
  const runningElsewhere = Boolean(active.data) && !runningHere;
  const total = summary.data && summary.data.total_seconds > 0 ? ` · 累计 ${formatDuration(Math.round(summary.data.total_seconds / 60))}（${summary.data.session_count} 次）` : '';

  return (
    <div className="focus-controls">
      <button
        className={runningHere ? 'ghost sm' : 'ghost sm'}
        type="button"
        disabled={toggle.isPending || runningElsewhere}
        title={runningElsewhere ? `另一事项「${active.data?.item_title}」计时中` : runningHere ? '停止专注计时' : '开始专注计时'}
        onClick={() => toggle.mutate(runningHere)}
      >
        {runningHere ? <Square size={13} /> : <Play size={13} />}
        {runningHere ? ' 停止专注' : ' 开始专注'}
      </button>
      {toggle.isError && <p className="error-line">{toggle.error.message}</p>}
      {total && <span className="hint focus-total">{total}</span>}
    </div>
  );
}

/** 全局悬浮计时条：跨页/刷新不丢（服务端为真源）。 */
export function FocusBar({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const active = useQuery({ queryKey: ['focus', 'active'], queryFn: api.activeFocus, refetchInterval: 30000 });
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!active.data) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active.data]);

  const stop = useMutation({
    mutationFn: (complete: boolean) => api.stopFocus(session.csrf_token, active.data!.item_id).then((sessionResult) => ({ sessionResult, complete })),
    onSuccess: async ({ complete }) => {
      if (complete && active.data) {
        const cached = [...((queryClient.getQueryData(['items', 'work']) as Item[] | undefined) ?? []), ...((queryClient.getQueryData(['items', 'personal']) as Item[] | undefined) ?? [])];
        const item = cached.find((candidate) => candidate.id === active.data!.item_id);
        if (item) {
          await api.patchItem(session.csrf_token, item, { status: 'done' });
          queryClient.invalidateQueries({ queryKey: ['items'] });
        }
      }
      queryClient.invalidateQueries({ queryKey: ['focus'] });
    },
  });

  if (!active.data) return null;

  const elapsedSeconds = Math.max(0, Math.floor((now - new Date(active.data.started_at).getTime()) / 1000));
  const mm = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
  const ss = String(elapsedSeconds % 60).padStart(2, '0');

  return (
    <div className="focus-bar" role="status">
      <Circle size={8} className="focus-pulse" />
      <span className="focus-bar-title">{active.data.item_title}</span>
      <span className="focus-bar-time">{mm}:{ss}</span>
      <button className="ghost sm" type="button" disabled={stop.isPending} onClick={() => stop.mutate(true)} title="停止计时并标记完成">
        完成
      </button>
      <button className="ghost sm" type="button" disabled={stop.isPending} onClick={() => stop.mutate(false)} title="仅停止计时">
        停止
      </button>
    </div>
  );
}
