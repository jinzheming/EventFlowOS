import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { api, IdentityScopeRule, PatCreated, Person, Preferences, Session, WebhookCreatedSub } from '../api/client';
import { formatUpdatedAt } from '../lib/dates';
import { scopeLabel } from '../lib/labels';

function identityLabel(identity: string | null) {
  return identity?.trim() || '未设置身份';
}

export function SettingsPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const [section, setSection] = useState<'people' | 'prefs' | 'data' | 'trash' | 'mcp' | 'webhook'>('people');
  const [addingPerson, setAddingPerson] = useState(false);
  const people = useQuery({ queryKey: ['people'], queryFn: () => api.people(true) });
  const [name, setName] = useState('');
  const [identity, setIdentity] = useState('');
  const [note, setNote] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Pick<Person, 'name' | 'identity' | 'note' | 'active'>>>({});

  const createPerson = useMutation({
    mutationFn: () => api.createPerson(session.csrf_token, { name: name.trim(), identity: identity.trim() || null, note: note.trim() || null }),
    onSuccess: () => {
      setName('');
      setIdentity('');
      setNote('');
      queryClient.invalidateQueries({ queryKey: ['people'] });
    },
  });

  const patchPerson = useMutation({
    mutationFn: ({ person, patch }: { person: Person; patch: Partial<Pick<Person, 'name' | 'identity' | 'note' | 'active'>> }) =>
      api.patchPerson(session.csrf_token, person.id, patch),
    onSuccess: () => {
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ['people'] });
    },
  });

  const deletePerson = useMutation({
    mutationFn: (person: Person) => api.deletePerson(session.csrf_token, person.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['people'] }),
  });

  const grouped = useMemo(() => {
    const groups = new Map<string, Person[]>();
    for (const person of people.data ?? []) {
      const key = person.active ? identityLabel(person.identity) : '已停用';
      groups.set(key, [...(groups.get(key) ?? []), person]);
    }
    return [...groups.entries()];
  }, [people.data]);

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) createPerson.mutate();
  }

  function startEdit(person: Person) {
    setEditingId(person.id);
    setDrafts((current) => ({
      ...current,
      [person.id]: { name: person.name, identity: person.identity, note: person.note, active: person.active },
    }));
  }

  function updateDraft(personId: string, patch: Partial<Pick<Person, 'name' | 'identity' | 'note' | 'active'>>) {
    setDrafts((current) => ({ ...current, [personId]: { ...current[personId], ...patch } }));
  }

  function saveEdit(person: Person) {
    const draft = drafts[person.id];
    if (!draft?.name.trim()) return;
    patchPerson.mutate({
      person,
      patch: {
        name: draft.name.trim(),
        identity: draft.identity?.trim() || null,
        note: draft.note?.trim() || null,
        active: draft.active,
      },
    });
  }

  return (
    <section className="page settings-page">
      <header className="page-header">
        <div>
          <h1>设置</h1>
          <p>人员、偏好与通知、数据备份与回收站</p>
        </div>
      </header>

      <div className="page-tabs" role="tablist">
        {SETTINGS_TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={section === tab.id}
            className={section === tab.id ? 'page-tab active' : 'page-tab'}
            type="button"
            onClick={() => setSection(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {section === 'people' && (
          <section className="settings-card">
            <div className="card-head">
              <h2>人员</h2>
              <button className="ghost sm" type="button" onClick={() => setAddingPerson((open) => !open)}>
                <Plus size={14} /> 添加人员
              </button>
            </div>
            {addingPerson && (
              <form className="person-form" onSubmit={submitCreate}>
                <input placeholder="姓名（必填）" value={name} onChange={(event) => setName(event.target.value)} />
                <input placeholder="身份（可选，自定义，如同事/家人/供应商）" value={identity} onChange={(event) => setIdentity(event.target.value)} />
                <input className="person-form-note" placeholder="备注（可选）" value={note} onChange={(event) => setNote(event.target.value)} />
                <div className="panel-actions">
                  <button className="ghost sm" type="button" onClick={() => setAddingPerson(false)}>取消</button>
                  <button className="primary" type="submit" disabled={!name.trim() || createPerson.isPending}>
                    <Plus size={16} /> 添加
                  </button>
                </div>
              </form>
            )}
            {createPerson.isError && <p className="error-line">{createPerson.error.message}</p>}
            {people.isLoading && <p className="hint">加载中…</p>}
            {people.isError && <p className="error-line">{people.error.message}</p>}
            {grouped.map(([group, rows]) => (
              <div className="person-group" key={group}>
                <h3>{group}</h3>
                <div className="person-directory-list">
                  {rows.map((person) => {
                    const editing = editingId === person.id;
                    const draft = drafts[person.id] ?? { name: person.name, identity: person.identity, note: person.note, active: person.active };
                    return (
                      <article className={person.active ? 'person-directory-row' : 'person-directory-row inactive'} key={person.id}>
                        {editing ? (
                          <>
                            <input value={draft.name} onChange={(event) => updateDraft(person.id, { name: event.target.value })} />
                            <input value={draft.identity ?? ''} placeholder="身份（可选）" onChange={(event) => updateDraft(person.id, { identity: event.target.value })} />
                            <input value={draft.note ?? ''} placeholder="备注" onChange={(event) => updateDraft(person.id, { note: event.target.value })} />
                            <label className="toggle-line compact">
                              <input type="checkbox" checked={draft.active} onChange={(event) => updateDraft(person.id, { active: event.target.checked })} />
                              启用
                            </label>
                            <div className="row-actions">
                              <button className="ghost sm" type="button" onClick={() => setEditingId(null)}>取消</button>
                              <button className="primary" type="button" onClick={() => saveEdit(person)} disabled={patchPerson.isPending || !draft.name.trim()}>保存</button>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="person-info">
                              <strong>{person.name}</strong>
                              {person.note && <span className="person-note">{person.note}</span>}
                              <span className="muted person-count">{person.item_count} 个事项</span>
                            </div>
                            <div className="row-actions">
                              <button className="ghost sm" type="button" onClick={() => startEdit(person)}>编辑</button>
                              <button className="ghost sm" type="button" onClick={() => patchPerson.mutate({ person, patch: { active: !person.active } })}>
                                {person.active ? '停用' : '启用'}
                              </button>
                              <button className="ghost sm danger-text" type="button" aria-label="删除" onClick={() => deletePerson.mutate(person)} disabled={person.item_count > 0 || deletePerson.isPending} title={person.item_count > 0 ? '已被事项引用，请停用' : '删除'}>
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </>
                        )}
                      </article>
                    );
                  })}
                </div>
              </div>
            ))}
            {patchPerson.isError && <p className="error-line">{patchPerson.error.message}</p>}
            {deletePerson.isError && <p className="error-line">{deletePerson.error.message}</p>}
          </section>
      )}
      {section === 'prefs' && <PrefsSection session={session} />}
      {section === 'data' && <DataSection session={session} />}
      {section === 'trash' && <TrashSection session={session} />}
      {section === 'mcp' && <McpSection session={session} />}
      {section === 'webhook' && <WebhookSection session={session} />}
    </section>
  );
}

const SETTINGS_TABS: Array<{ id: 'people' | 'prefs' | 'data' | 'trash' | 'mcp' | 'webhook'; label: string }> = [
  { id: 'people', label: '人员' },
  { id: 'prefs', label: '偏好与通知' },
  { id: 'data', label: '数据' },
  { id: 'trash', label: '回收站' },
  { id: 'mcp', label: 'MCP' },
  { id: 'webhook', label: 'Webhook' },
];

const TIMEZONE_OPTIONS = [
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Taipei',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Urumqi',
  'UTC',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Australia/Sydney',
];

function copyText(text: string, mark: (v: boolean) => void) {
  navigator.clipboard.writeText(text).then(() => {
    mark(true);
    window.setTimeout(() => mark(false), 2000);
  });
}

function SwitchControl({ on, disabled, onToggle }: { on: boolean; disabled?: boolean; onToggle: () => void }) {
  return (
    <button className={on ? 'switch on' : 'switch'} type="button" role="switch" aria-checked={on} disabled={disabled} onClick={onToggle}>
      <span className="switch-knob" />
    </button>
  );
}

function PrefsSection({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const prefs = useQuery({ queryKey: ['preferences'], queryFn: api.preferences });
  const health = useQuery({ queryKey: ['reminder-health'], queryFn: api.reminderHealth, refetchInterval: 60000 });
  const channels = useQuery({ queryKey: ['reminder-channels'], queryFn: api.reminderChannels });
  const patch = useMutation({
    mutationFn: (payload: Partial<Preferences>) => api.patchPreferences(session.csrf_token, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['preferences'], data);
      queryClient.invalidateQueries({ queryKey: ['session'] });
    },
  });

  const [desktopHint, setDesktopHint] = useState<string | null>(null);

  async function toggleDesktopWithPermission(enabled: boolean) {
    if (enabled && 'Notification' in window) {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setDesktopHint('通知权限未授予：请在浏览器地址栏允许本站通知后重试');
        return;
      }
      setDesktopHint(null);
    }
    patch.mutate({ desktop_notifications: enabled });
  }

  const currentTimezone = prefs.data?.timezone ?? '';
  const timezoneOptions = currentTimezone && !TIMEZONE_OPTIONS.includes(currentTimezone)
    ? [currentTimezone, ...TIMEZONE_OPTIONS]
    : TIMEZONE_OPTIONS;

  return (
    <>
      <section className="settings-card">
        <h2>偏好</h2>
        {prefs.isLoading && <p className="hint">加载中…</p>}
        {prefs.isError && <p className="error-line">{prefs.error.message}</p>}
        {prefs.data && (
          <label className="toggle-line">
            时区
            <select
              value={currentTimezone}
              disabled={patch.isPending}
              onChange={(event) => patch.mutate({ timezone: event.target.value })}
            >
              {timezoneOptions.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </label>
        )}
        {patch.isError && <p className="error-line">{patch.error.message}</p>}
        <p className="hint">时区影响「今天/明天」的判定、全天事项提醒时间与所有时间显示，保存后立即生效。</p>
        {prefs.data && <IdentityRulesEditor rules={prefs.data.identity_scope_rules} saving={patch.isPending} onSave={(rules) => patch.mutate({ identity_scope_rules: rules })} />}
      </section>

      <section className="settings-card">
        <h2>通知渠道</h2>
        <div className="settings-row-list">
          <div className="settings-row">
            <div className="settings-row-info">
              <strong>应用内提醒</strong>
              <span>站内通知中心与悬浮提示</span>
            </div>
            <span className="state-badge on">始终开启</span>
          </div>
          <div className="settings-row">
            <div className="settings-row-info">
              <strong>桌面通知</strong>
              <span>浏览器系统通知（需保持页面后台运行）</span>
            </div>
            {'Notification' in window ? (
              <SwitchControl
                on={prefs.data?.desktop_notifications ?? false}
                disabled={patch.isPending}
                onToggle={() => toggleDesktopWithPermission(!prefs.data?.desktop_notifications)}
              />
            ) : (
              <span className="state-badge">浏览器不支持</span>
            )}
          </div>
          {desktopHint && <p className="hint settings-hint-line">{desktopHint}</p>}
          <div className="settings-row">
            <div className="settings-row-info">
              <strong>周复盘</strong>
              <span>导航中显示「复盘」页</span>
            </div>
            <SwitchControl
              on={prefs.data?.weekly_review_enabled ?? false}
              disabled={patch.isPending}
              onToggle={() => patch.mutate({ weekly_review_enabled: !(prefs.data?.weekly_review_enabled ?? false) })}
            />
          </div>
          <div className="settings-row">
            <div className="settings-row-info">
              <strong>早报摘要</strong>
              <span>今日速览（定时事项、逾期、等待跟进与习惯打卡），无内容时自动静默</span>
            </div>
            <div className="settings-row-controls">
              <input
                type="time"
                value={prefs.data?.digest_morning_time ?? '08:00'}
                disabled={patch.isPending || !(prefs.data?.digest_morning_enabled ?? true)}
                onChange={(event) => patch.mutate({ digest_morning_time: event.target.value })}
              />
              <SwitchControl
                on={prefs.data?.digest_morning_enabled ?? true}
                disabled={patch.isPending}
                onToggle={() => patch.mutate({ digest_morning_enabled: !(prefs.data?.digest_morning_enabled ?? true) })}
              />
            </div>
          </div>
          <div className="settings-row">
            <div className="settings-row-info">
              <strong>晚报摘要</strong>
              <span>今日总结（完成情况、专注时长、打卡率与次日安排），无内容时自动静默</span>
            </div>
            <div className="settings-row-controls">
              <input
                type="time"
                value={prefs.data?.digest_evening_time ?? '21:00'}
                disabled={patch.isPending || !(prefs.data?.digest_evening_enabled ?? false)}
                onChange={(event) => patch.mutate({ digest_evening_time: event.target.value })}
              />
              <SwitchControl
                on={prefs.data?.digest_evening_enabled ?? false}
                disabled={patch.isPending}
                onToggle={() => patch.mutate({ digest_evening_enabled: !(prefs.data?.digest_evening_enabled ?? false) })}
              />
            </div>
          </div>
          <div className="settings-row">
            <div className="settings-row-info">
              <strong>外部推送（飞书 / ntfy）</strong>
              <span>在事项抽屉勾选「同时发送外部通知」后随提醒投递；渠道由服务端环境变量配置</span>
            </div>
            <div className="settings-row-controls">
              <span className={channels.data?.feishu_configured ? 'state-badge on' : 'state-badge warn'}>飞书 {channels.data?.feishu_configured ? '已配置' : '未配置'}</span>
              <span className={channels.data?.ntfy_configured ? 'state-badge on' : 'state-badge warn'}>ntfy {channels.data?.ntfy_configured ? '已配置' : '未配置'}</span>
            </div>
          </div>
          <div className="settings-row">
            <WebPushToggle session={session} />
          </div>
        </div>
      </section>

      <section className="settings-card">
        <h2>运行诊断</h2>
        {health.isLoading && <p className="hint">加载中…</p>}
        {health.isError && <p className="error-line">{health.error.message}</p>}
        {health.data && (
          <div className="person-directory-list">
            <article className="person-directory-row">
              <div className="person-info">
                <strong>{health.data.worker_seen_recently ? '运行中' : '未见心跳'}</strong>
                <span>
                  待投递 {health.data.pending_count} · 重试中 {health.data.retry_count} · 需人工处理 {health.data.dead_count}
                  {health.data.max_lag_seconds !== null ? ` · 最大延迟 ${Math.round(health.data.max_lag_seconds)}s` : ''}
                </span>
              </div>
            </article>
            {!health.data.worker_seen_recently && (
              <p className="error-line">提醒 worker 心跳缺失：请检查服务器上的 worker 进程，否则到点提醒不会投递。</p>
            )}
          </div>
        )}
      </section>
    </>
  );
}

function urlBase64ToUint8Array(base64: string) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(normalized);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

function WebPushToggle({ session }: { session: Session }) {
  const vapid = useQuery({ queryKey: ['push-vapid'], queryFn: api.pushVapidKey });
  const [enabled, setEnabled] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const pushSupported = typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window;

  useEffect(() => {
    if (!pushSupported) return;
    navigator.serviceWorker.ready
      .then((registration) => registration.pushManager.getSubscription())
      .then((subscription) => setEnabled(Boolean(subscription)))
      .catch(() => undefined);
  }, [pushSupported]);

  async function subscribe() {
    setHint(null);
    if (!pushSupported) {
      setHint('当前浏览器或访问方式不支持 Web Push（需要 HTTPS 或 localhost）');
      return;
    }
    const key = vapid.data;
    if (!key?.enabled || !key.public_key) {
      setHint('服务器未配置 VAPID 密钥，Web Push 不可用');
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      setHint('通知权限未授予');
      return;
    }
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key.public_key),
    });
    const json = subscription.toJSON();
    await api.subscribePush(session.csrf_token, {
      endpoint: subscription.endpoint,
      p256dh: json.keys?.p256dh ?? '',
      auth: json.keys?.auth ?? '',
    });
    setEnabled(true);
  }

  async function unsubscribe() {
    setHint(null);
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      await api.unsubscribePush(session.csrf_token, subscription.endpoint);
      await subscription.unsubscribe();
    }
    setEnabled(false);
  }

  return (
    <>
      <div className="person-info">
        <strong>Web Push 系统通知</strong>
        <span>浏览器/系统级推送，页面关闭也能收到提醒；需在 HTTPS 或 localhost 下访问</span>
        {vapid.data && !vapid.data.enabled && <span className="hint">服务器未配置 VAPID 密钥</span>}
        {!pushSupported && <span className="hint">当前访问方式不支持（需 HTTPS 或 localhost）</span>}
        {hint && <span className="error-line">{hint}</span>}
      </div>
      <div className="row-actions">
        <label className="toggle-line compact">
          <input
            type="checkbox"
            checked={enabled}
            disabled={vapid.isLoading || !pushSupported}
            onChange={(event) => {
              if (event.target.checked) {
                void subscribe().catch((err: Error) => setHint(err.message));
              } else {
                void unsubscribe().catch((err: Error) => setHint(err.message));
              }
            }}
          />
          {enabled ? '已开启' : '开启'}
        </label>
      </div>
    </>
  );
}

function DataSection({ session }: { session: Session }) {
  return (
    <>
      <section className="settings-card">
        <h2>数据导出</h2>
        <p className="hint">导出全部事项、项目、里程碑、标签、人员、提醒规则与偏好为 JSON 文件，可用于备份或迁移。</p>
        <button className="primary" type="button" onClick={() => window.open('/api/v1/export', '_blank')}>
          导出全部数据（JSON）
        </button>
      </section>
      <IcsCard session={session} />
    </>
  );
}

function IcsCard({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const prefs = useQuery({ queryKey: ['preferences'], queryFn: api.preferences });
  const [copied, setCopied] = useState(false);
  const regenerate = useMutation({
    mutationFn: () => api.regenerateFeedToken(session.csrf_token),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['preferences'] }),
  });

  const feedUrl = prefs.data?.ics_token ? `${window.location.origin}/api/v1/calendar/feed.ics?token=${prefs.data.ics_token}` : null;
  const webcalUrl = feedUrl ? feedUrl.replace(/^https?:/, 'webcal:') : null;

  return (
    <section className="settings-card">
      <h2>日历订阅（ICS）</h2>
      <p className="hint">
        只读订阅：事项/里程碑的修改与删除会在日历客户端下次拉取时同步（Apple 日历约 5–15 分钟，飞书/Google 数小时，取决于客户端刷新策略）。
      </p>
      {webcalUrl ? (
        <>
          <div className="ics-url-row">
            <input readOnly value={webcalUrl} onFocus={(event) => event.target.select()} />
            <button
              className="ghost sm"
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(webcalUrl).then(() => {
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 2000);
                });
              }}
            >
              {copied ? '已复制' : '复制'}
            </button>
          </div>
          <div className="panel-actions">
            <button className="ghost sm danger-text" type="button" disabled={regenerate.isPending} onClick={() => regenerate.mutate()}>
              重置令牌（旧链接立即失效）
            </button>
          </div>
        </>
      ) : (
        <button className="primary" type="button" disabled={regenerate.isPending || prefs.isLoading} onClick={() => regenerate.mutate()}>
          生成订阅链接
        </button>
      )}
      {regenerate.isError && <p className="error-line">{regenerate.error.message}</p>}
    </section>
  );
}

function TrashSection({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const trash = useQuery({ queryKey: ['items-trash'], queryFn: api.trashedItems });
  const [error, setError] = useState<string | null>(null);

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ['items-trash'] });
    queryClient.invalidateQueries({ queryKey: ['items'] });
    queryClient.invalidateQueries({ queryKey: ['calendar'] });
  }

  const restore = useMutation({
    mutationFn: (itemId: string) => api.restoreDeletedItem(session.csrf_token, itemId),
    onSuccess: invalidateAll,
    onError: (err) => setError(err.message),
  });
  const purge = useMutation({
    mutationFn: (itemId: string) => api.purgeItem(session.csrf_token, itemId),
    onSuccess: invalidateAll,
    onError: (err) => setError(err.message),
  });

  return (
    <section className="settings-card">
      <h2>回收站</h2>
      <p className="hint">删除的事项保留在这里，可随时恢复；彻底清除后不可恢复。</p>
      {trash.isLoading && <p className="hint">加载中…</p>}
      {trash.isError && <p className="error-line">{trash.error.message}</p>}
      {trash.data?.length === 0 && <p className="empty">回收站为空</p>}
      <div className="person-directory-list">
        {(trash.data ?? []).map((item) => (
          <article className="person-directory-row" key={item.id}>
            <div>
              <strong>{item.title}</strong>
              <span>
                {scopeLabel(item.scope)} · 删除于 {formatUpdatedAt(item.deleted_at ?? item.updated_at)}
              </span>
            </div>
            <button className="secondary" type="button" disabled={restore.isPending} onClick={() => restore.mutate(item.id)}>
              恢复
            </button>
            <button
              className="danger"
              type="button"
              disabled={purge.isPending}
              onClick={() => {
                if (window.confirm(`彻底清除「${item.title}」？此操作不可恢复。`)) purge.mutate(item.id);
              }}
            >
              彻底清除
            </button>
          </article>
        ))}
      </div>
      {error && <p className="error-line">{error}</p>}
    </section>
  );
}

function IdentityRulesEditor({
  rules,
  saving,
  onSave,
}: {
  rules: IdentityScopeRule[];
  saving: boolean;
  onSave: (rules: IdentityScopeRule[]) => void;
}) {
  const [draft, setDraft] = useState<IdentityScopeRule[]>(rules);
  const [newKeyword, setNewKeyword] = useState('');
  const [newScope, setNewScope] = useState<'work' | 'personal'>('work');

  useEffect(() => setDraft(rules), [rules]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(rules);

  return (
    <div className="identity-rules">
      <h3>协作者身份归类</h3>
      <p className="hint">快速录入识别 @人名 / !人名 时，依据人员档案中的「身份」自动匹配范围；未命中规则时归入收集箱。</p>
      {draft.map((rule, index) => (
        <div className="identity-rule-row" key={`${rule.keyword}-${index}`}>
          <span className="identity-rule-keyword">{rule.keyword}</span>
          <select
            value={rule.scope}
            disabled={saving}
            onChange={(event) => {
              const next = [...draft];
              next[index] = { ...rule, scope: event.target.value as 'work' | 'personal' };
              setDraft(next);
            }}
          >
            <option value="work">工作</option>
            <option value="personal">个人</option>
          </select>
          <button className="ghost sm danger-text" type="button" title="删除规则" disabled={saving} onClick={() => setDraft(draft.filter((_, i) => i !== index))}>
            <Trash2 size={13} />
          </button>
        </div>
      ))}
      <div className="identity-rule-row">
        <input placeholder="关键词（如：同事）" value={newKeyword} onChange={(event) => setNewKeyword(event.target.value)} />
        <select value={newScope} onChange={(event) => setNewScope(event.target.value as 'work' | 'personal')}>
          <option value="work">工作</option>
          <option value="personal">个人</option>
        </select>
        <button
          className="ghost sm"
          type="button"
          disabled={saving || !newKeyword.trim() || draft.some((rule) => rule.keyword === newKeyword.trim())}
          onClick={() => {
            setDraft([...draft, { keyword: newKeyword.trim(), scope: newScope }]);
            setNewKeyword('');
          }}
        >
          <Plus size={13} /> 添加
        </button>
      </div>
      {dirty && (
        <div className="panel-actions">
          <button className="ghost sm" type="button" disabled={saving} onClick={() => setDraft(rules)}>还原</button>
          <button className="primary" type="button" disabled={saving} onClick={() => onSave(draft)}>保存规则</button>
        </div>
      )}
    </div>
  );
}

function McpSection({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const tokens = useQuery({ queryKey: ['pat-tokens'], queryFn: () => api.patTokens() });
  const [name, setName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState('365');
  const [scopes, setScopes] = useState<string[]>(['read', 'write']);
  const [created, setCreated] = useState<PatCreated | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const createToken = useMutation({
    mutationFn: (payload: { name: string; scopes: string[]; expires_in_days?: number }) =>
      api.createPatToken(session.csrf_token, payload),
    onSuccess: (token) => {
      setCreated(token);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['pat-tokens'] });
    },
    onError: (err) => setError(err.message),
  });
  const revoke = useMutation({
    mutationFn: (tokenId: string) => api.revokePatToken(session.csrf_token, tokenId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pat-tokens'] }),
    onError: (err) => setError(err.message),
  });

  const mcpUrl = 'http://127.0.0.1:18099/mcp';
  const configSnippet = created
    ? JSON.stringify(
        {
          mcpServers: {
            'personal-affairs': {
              url: mcpUrl,
              env: { PERSONAL_AFFAIRS_MCP_TOKEN: created.token },
            },
          },
        },
        null,
        2,
      )
    : '';

  function toggleScope(scope: string) {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  }

  const [endpointCopied, setEndpointCopied] = useState(false);

  return (
    <>
      <section className="settings-card">
        <h2>MCP 接入（Agent 原生）</h2>
        <p className="hint">AI agent（Claude / Codex 等）可通过 MCP 读写事项、人员与提醒，并查询/写入日程。端点仅服务器本地/Tailnet 内可达：</p>
        <div className="endpoint-row">
          <code>{mcpUrl}</code>
          <button className="ghost sm" type="button" onClick={() => copyText(mcpUrl, setEndpointCopied)}>
            {endpointCopied ? '已复制' : '复制'}
          </button>
        </div>

        <div className="form-grid">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="令牌名称，如 codex-cli" />
          <select value={expiresInDays} onChange={(event) => setExpiresInDays(event.target.value)}>
            <option value="30">30 天</option>
            <option value="90">90 天</option>
            <option value="365">365 天</option>
            <option value="">永不过期</option>
          </select>
          <div className="chip-multi">
            {(['read', 'write'] as const).map((scope) => (
              <button
                key={scope}
                type="button"
                className={scopes.includes(scope) ? 'chip active' : 'chip'}
                onClick={() => toggleScope(scope)}
              >
                {scope === 'read' ? '读' : '写'}
              </button>
            ))}
          </div>
          <button
            className="primary"
            type="button"
            disabled={createToken.isPending || !name.trim() || scopes.length === 0}
            onClick={() =>
              createToken.mutate({
                name: name.trim(),
                scopes,
                ...(expiresInDays ? { expires_in_days: Number(expiresInDays) } : {}),
              })
            }
          >
            创建令牌
          </button>
        </div>
        {error && <p className="error-line">{error}</p>}

        {created && (
          <div className="secret-reveal">
            <p className="secret-reveal-title">令牌仅显示一次，请立即复制保存</p>
            <div className="secret-row">
              <code>{created.token}</code>
              <button className="ghost sm" type="button" onClick={() => copyText(created.token, setCopied)}>
                {copied ? '已复制' : '复制令牌'}
              </button>
            </div>
            <textarea
              readOnly
              value={configSnippet}
              rows={8}
              onFocus={(event) => event.target.select()}
            />
            <div className="panel-actions">
              <button className="ghost sm" type="button" onClick={() => copyText(configSnippet, setCopied)}>
                复制 Claude 配置
              </button>
              <button className="ghost sm" type="button" onClick={() => setCreated(null)}>
                我已保存，关闭
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="settings-card">
        <h2>已创建的令牌</h2>
        {tokens.isLoading && <p className="hint">加载中…</p>}
        {tokens.data && tokens.data.length === 0 && <p className="hint">尚未创建令牌。</p>}
        <div className="settings-row-list">
          {tokens.data?.map((token) => {
            const revoked = Boolean(token.revoked_at);
            return (
              <div key={token.id} className={revoked ? 'settings-row inactive' : 'settings-row'}>
                <div className="settings-row-info">
                  <strong>{token.name}{revoked ? '（已吊销）' : ''}</strong>
                  <span>{token.scopes.map((sc) => (sc === 'read' ? '读' : '写')).join(' / ')}</span>
                </div>
                <span className="state-badge">{token.expires_at ? `至 ${formatUpdatedAt(token.expires_at)}` : '永不过期'}</span>
                {!revoked && (
                  <button className="ghost sm danger-text" type="button" disabled={revoke.isPending} onClick={() => revoke.mutate(token.id)}>
                    吊销
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

const WEBHOOK_EVENT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'item.created', label: '事项创建' },
  { value: 'item.completed', label: '事项完成' },
  { value: 'reminder.fired', label: '提醒触发' },
  { value: 'reminder.acked', label: '提醒确认' },
  { value: 'reminder.snoozed', label: '提醒推迟' },
  { value: 'delivery.failed', label: '投递失败（死信）' },
];

const WEBHOOK_STATUS_LABEL: Record<string, string> = {
  published: '已投递',
  delivering: '投递中',
  retrying: '重试中',
  dead: '死信',
  pending: '待投递',
};

function WebhookSection({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const hooks = useQuery({ queryKey: ['webhooks'], queryFn: () => api.webhooks() });
  const events = useQuery({ queryKey: ['webhook-events'], queryFn: () => api.webhookEvents(20) });
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [created, setCreated] = useState<WebhookCreatedSub | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const createHook = useMutation({
    mutationFn: (payload: { name: string; url: string; events: string[] }) =>
      api.createWebhook(session.csrf_token, payload),
    onSuccess: (hook) => {
      setCreated(hook);
      setError(null);
      setName('');
      setUrl('');
      setSelected([]);
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
    onError: (err) => setError(err.message),
  });
  const removeHook = useMutation({
    mutationFn: (webhookId: string) => api.deleteWebhook(session.csrf_token, webhookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      queryClient.invalidateQueries({ queryKey: ['webhook-events'] });
    },
    onError: (err) => setError(err.message),
  });

  function toggleEvent(value: string) {
    setSelected((prev) => (prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]));
  }

  const statusTone = (status: string) => (status === 'dead' ? 'danger' : status === 'retrying' || status === 'delivering' ? 'warn' : 'on');

  return (
    <>
      <section className="settings-card">
        <h2>Webhook 订阅（联合调度出站）</h2>
        <p className="hint">
          订阅事件后，触发时系统会以 HMAC 签名 POST 到你的端点（n8n / activepieces / 自写脚本等）。请求头含{' '}
          <code>X-PA-Signature</code>、<code>X-PA-Event-Id</code>（幂等键）、<code>X-PA-Event-Type</code>、<code>X-PA-Retry-Count</code>
          ；请按 <code>X-PA-Event-Id</code> 去重（at-least-once 投递）。
        </p>

        <div className="form-grid">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="订阅名称，如 n8n" />
          <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="回调 URL，如 http://10.0.0.8:5678/webhook/pa" />
          <div className="chip-multi">
            {WEBHOOK_EVENT_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={selected.includes(option.value) ? 'chip active' : 'chip'}
                onClick={() => toggleEvent(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            className="primary"
            type="button"
            disabled={createHook.isPending || !name.trim() || !url.trim() || selected.length === 0}
            onClick={() => createHook.mutate({ name: name.trim(), url: url.trim(), events: selected })}
          >
            创建订阅
          </button>
        </div>
        {error && <p className="error-line">{error}</p>}

        {created && (
          <div className="secret-reveal">
            <p className="secret-reveal-title">密钥仅显示一次（用于校验 X-PA-Signature），请立即复制保存</p>
            <div className="secret-row">
              <code>{created.secret}</code>
              <button className="ghost sm" type="button" onClick={() => copyText(created.secret, setCopied)}>
                {copied ? '已复制' : '复制密钥'}
              </button>
            </div>
            <div className="panel-actions">
              <button className="ghost sm" type="button" onClick={() => setCreated(null)}>
                我已保存，关闭
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="settings-card">
        <h2>已创建的订阅</h2>
        {hooks.isLoading && <p className="hint">加载中…</p>}
        {hooks.data && hooks.data.length === 0 && <p className="hint">尚未创建订阅。</p>}
        <div className="settings-row-list">
          {hooks.data?.map((hook) => (
            <div key={hook.id} className="settings-row">
              <div className="settings-row-info">
                <strong>{hook.name}</strong>
                <span>{hook.url}</span>
              </div>
              <span className="state-badge on">{hook.events.length} 个事件</span>
              <button className="ghost sm danger-text" type="button" disabled={removeHook.isPending} onClick={() => removeHook.mutate(hook.id)}>
                删除
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="settings-card">
        <h2>最近事件</h2>
        <p className="hint">最近 20 条出站事件与投递状态。</p>
        {events.isLoading && <p className="hint">加载中…</p>}
        {events.data && events.data.length === 0 && <p className="hint">暂无事件。</p>}
        <div className="settings-row-list">
          {events.data?.map((event) => (
            <div key={event.id} className="settings-row">
              <div className="settings-row-info">
                <strong>{WEBHOOK_EVENT_OPTIONS.find((o) => o.value === event.event_type)?.label ?? event.event_type}</strong>
                <span>{formatUpdatedAt(event.created_at)}{event.attempt_count > 1 ? ` · 尝试 ${event.attempt_count} 次` : ''}</span>
              </div>
              <span className={`state-badge ${statusTone(event.status)}`}>{WEBHOOK_STATUS_LABEL[event.status] ?? event.status}</span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
