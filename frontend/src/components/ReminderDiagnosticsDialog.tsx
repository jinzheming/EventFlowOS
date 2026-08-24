import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { useMemo, useRef } from 'react';
import { api, ReminderDelivery, Session } from '../api/client';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { formatScheduleTime } from '../lib/dates';

export function ReminderDiagnosticsDialog({ session, onClose }: { session: Session; onClose: () => void }) {
  const queryClient = useQueryClient();
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogA11y(panelRef, onClose);
  const dead = useQuery({ queryKey: ['reminder-deliveries', 'dead'], queryFn: () => api.reminderDeliveries(undefined, 'dead') });
  const retryWait = useQuery({ queryKey: ['reminder-deliveries', 'retry_wait'], queryFn: () => api.reminderDeliveries(undefined, 'retry_wait') });
  // 与 ReminderInbox 相同的 query key：命中缓存，不产生额外请求
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });

  const itemTitleById = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of [...(workItems.data ?? []), ...(personalItems.data ?? [])]) map.set(item.id, item.title);
    return map;
  }, [workItems.data, personalItems.data]);

  const retryMutation = useMutation({
    mutationFn: (deliveryId: string) => api.retryDelivery(session.csrf_token, deliveryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminder-deliveries'] });
      queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
    },
  });

  function renderRow(delivery: ReminderDelivery) {
    return (
      <article className="diag-row" key={delivery.id}>
        <div>
          <strong>{itemTitleById.get(delivery.item_id) ?? '未知事项'}</strong>
          <small>
            {delivery.channel} · {formatScheduleTime(delivery.scheduled_for)} · 已尝试 {delivery.attempt_count} 次
            {delivery.last_error_message ? ` · ${delivery.last_error_message}` : ''}
          </small>
        </div>
        {delivery.status === 'dead' && (
          <button className="ghost sm" type="button" disabled={retryMutation.isPending} onClick={() => retryMutation.mutate(delivery.id)}>
            重试
          </button>
        )}
      </article>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-panel diag-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="diag-title"
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="panel-header">
          <div>
            <p className="eyebrow">Reminders</p>
            <h2 id="diag-title">提醒投递诊断</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭" data-autofocus>
            <X size={16} />
          </button>
        </header>
        <section>
          <h3>需人工处理（dead）</h3>
          {dead.isLoading && <p className="hint">加载中…</p>}
          {dead.isError && <p className="error-line">{dead.error.message}</p>}
          {dead.data?.length === 0 && <p className="empty">暂无</p>}
          {dead.data?.map(renderRow)}
        </section>
        <section>
          <h3>等待重试（retry_wait）</h3>
          {retryWait.isLoading && <p className="hint">加载中…</p>}
          {retryWait.isError && <p className="error-line">{retryWait.error.message}</p>}
          {retryWait.data?.length === 0 && <p className="empty">暂无</p>}
          {retryWait.data?.map(renderRow)}
        </section>
        {retryMutation.isError && <p className="error-line">{retryMutation.error.message}</p>}
      </div>
    </div>
  );
}
