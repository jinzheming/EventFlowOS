import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pause, Play, Square } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, Session } from '../api/client';

const PAUSED_KEY = 'pa-focus-paused';

function readPaused(): string | null {
  try {
    return localStorage.getItem(PAUSED_KEY);
  } catch {
    return null;
  }
}

function fmtElapsed(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/**
 * 事项行内专注按钮：⏵ 开始 → 计时中（⏸ 暂停 / ⏹ 停止）→ 已暂停（▶ 继续 / ⏹ 结束）。
 * 暂停为本地语义：停表并记住本项，继续即重新开表；累计时长由服务端会话聚合，不受影响。
 */
export function RowFocusButton({ itemId, session }: { itemId: string; session: Session }) {
  const queryClient = useQueryClient();
  const active = useQuery({ queryKey: ['focus', 'active'], queryFn: api.activeFocus, refetchInterval: 30000 });
  const [pausedId, setPausedId] = useState<string | null>(readPaused);
  const [now, setNow] = useState(() => Date.now());

  const runningHere = active.data?.item_id === itemId;
  const runningElsewhere = Boolean(active.data) && !runningHere;
  const pausedHere = !active.data && pausedId === itemId;

  useEffect(() => {
    if (!runningHere) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [runningHere]);

  function persistPaused(id: string | null) {
    setPausedId(id);
    try {
      if (id) localStorage.setItem(PAUSED_KEY, id);
      else localStorage.removeItem(PAUSED_KEY);
    } catch {
      /* 私密模式忽略 */
    }
  }

  const act = useMutation({
    mutationFn: async (op: 'start' | 'pause' | 'stop' | 'resume' | 'discard') => {
      if (op === 'start' || op === 'resume') {
        await api.startFocus(session.csrf_token, itemId);
        persistPaused(null);
        return;
      }
      if (op === 'pause') {
        await api.stopFocus(session.csrf_token, itemId);
        persistPaused(itemId);
        return;
      }
      if (op === 'stop') await api.stopFocus(session.csrf_token, itemId);
      persistPaused(null);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['focus'] }),
  });

  const elapsed = runningHere && active.data ? Math.max(0, Math.floor((now - Date.parse(active.data.started_at)) / 1000)) : 0;

  if (runningHere) {
    return (
      <span className="row-focus running" onClick={(event) => event.stopPropagation()}>
        <span className="row-focus-elapsed" title="本次专注已计时">
          {fmtElapsed(elapsed)}
        </span>
        <button className="ghost sm" type="button" title="暂停（可稍后继续）" disabled={act.isPending} onClick={() => act.mutate('pause')}>
          <Pause size={12} />
        </button>
        <button className="ghost sm" type="button" title="停止专注" disabled={act.isPending} onClick={() => act.mutate('stop')}>
          <Square size={12} />
        </button>
      </span>
    );
  }

  if (pausedHere) {
    return (
      <span className="row-focus paused" onClick={(event) => event.stopPropagation()}>
        <button className="ghost sm" type="button" title="继续专注" disabled={act.isPending} onClick={() => act.mutate('resume')}>
          <Play size={12} /> 继续
        </button>
        <button className="ghost sm" type="button" title="结束（不再继续）" disabled={act.isPending} onClick={() => act.mutate('discard')}>
          <Square size={12} />
        </button>
      </span>
    );
  }

  return (
    <button
      className="ghost sm row-focus"
      type="button"
      title={runningElsewhere ? `另一事项「${active.data?.item_title}」计时中` : '开始专注计时'}
      disabled={act.isPending || runningElsewhere}
      onClick={(event) => {
        event.stopPropagation();
        act.mutate('start');
      }}
    >
      <Play size={12} /> 专注
    </button>
  );
}
