import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  api,
  ExternalBinding,
  ExternalBindingPayload,
  ExternalCapability,
  ExternalConflictPolicy,
  ExternalProfile,
  ExternalProfilePayload,
  ExternalProviderKey,
  ExternalScopeType,
  IdentityScopeRule,
  LLMBinding,
  LLMBindingPayload,
  LLMPrivacyTier,
  LLMProfile,
  LLMProfilePayload,
  LLMProviderKey,
  LLMScopeType,
  PatCreated,
  Person,
  Preferences,
  Session,
  WebhookCreatedSub,
  WriteTarget,
  WriteTargetFormat,
  WriteTargetPayload,
  WriteTargetType,
} from '../api/client';
import { formatUpdatedAt } from '../lib/dates';
import { scopeLabel } from '../lib/labels';

function identityLabel(identity: string | null) {
  return identity?.trim() || '未设置身份';
}

export function SettingsPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const [section, setSection] = useState<SettingsSection>('people');
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
      {section === 'external' && <ExternalProfilesSection session={session} />}
      {section === 'llm' && <LLMProfilesSection session={session} />}
      {section === 'targets' && <WriteTargetsSection session={session} />}
      {section === 'mcp' && <McpSection session={session} />}
      {section === 'webhook' && <WebhookSection session={session} />}
    </section>
  );
}

type SettingsSection = 'people' | 'prefs' | 'data' | 'trash' | 'external' | 'llm' | 'targets' | 'mcp' | 'webhook';

const SETTINGS_TABS: Array<{ id: SettingsSection; label: string }> = [
  { id: 'people', label: '人员' },
  { id: 'prefs', label: '偏好与通知' },
  { id: 'data', label: '数据' },
  { id: 'trash', label: '回收站' },
  { id: 'external', label: '外部集成' },
  { id: 'llm', label: 'AI 模型' },
  { id: 'targets', label: '写入目标' },
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

const FEISHU_WRITE_FIELD_MAPPING: Record<string, string> = {
  title: '事项名称',
  scope: '范围',
  status: '状态',
  priority: '优先级',
  schedule: '时间',
  project_name: '项目',
  notes: '备注',
  event_type: '事件',
  source_id: '来源ID',
  updated_at: '更新时间',
};

const WRITE_TARGET_TYPE_OPTIONS: Array<{ value: WriteTargetType; label: string }> = [
  { value: 'feishu_bitable', label: '飞书多维表格' },
  { value: 'custom', label: '自定义目标' },
];

const WRITE_TARGET_FORMAT_OPTIONS: Array<{ value: WriteTargetFormat; label: string }> = [
  { value: 'feishu_bitable_item_v1', label: '飞书事项记录 v1' },
  { value: 'compact_item_v1', label: '紧凑事项记录 v1' },
  { value: 'custom_json_v1', label: '自定义 JSON v1' },
];

function mappingText(mapping: Record<string, string>) {
  return JSON.stringify(mapping, null, 2);
}

function parseMapping(text: string): Record<string, string> {
  const parsed = JSON.parse(text || '{}') as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('字段映射必须是 JSON 对象，例如 {"title":"事项名称"}');
  }
  return Object.fromEntries(
    Object.entries(parsed).map(([key, value]) => [key, typeof value === 'string' ? value : String(value)]),
  );
}

function parseObject(text: string, label: string): Record<string, unknown> {
  const parsed = JSON.parse(text || '{}') as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return parsed as Record<string, unknown>;
}

const LLM_PROVIDER_OPTIONS: Array<{ value: LLMProviderKey; label: string }> = [
  { value: 'litellm', label: 'LiteLLM' },
  { value: 'openai_compatible', label: 'OpenAI-compatible' },
  { value: 'ollama', label: 'Ollama 本地' },
  { value: 'custom', label: '自定义' },
];

const LLM_PRIVACY_OPTIONS: Array<{ value: LLMPrivacyTier; label: string }> = [
  { value: 'standard', label: '标准' },
  { value: 'private', label: '本地/私有' },
  { value: 'sensitive', label: '敏感' },
];

const LLM_SCOPE_OPTIONS: Array<{ value: LLMScopeType; label: string }> = [
  { value: 'global', label: '全局' },
  { value: 'project', label: '项目' },
  { value: 'source_type', label: '来源类型' },
  { value: 'item_type', label: '事项类型' },
  { value: 'risk_tier', label: '风险等级' },
];

const DEFAULT_LLM_CAPABILITIES: Record<string, unknown> = {
  chat: true,
  json_object: true,
  tool_use: false,
  vision: false,
};

const DEFAULT_LLM_PARAMS: Record<string, unknown> = {
  temperature: 0,
  response_format: { type: 'json_object' },
};

function objectText(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2);
}

const EXTERNAL_PROVIDER_OPTIONS: Array<{ value: ExternalProviderKey; label: string }> = [
  { value: 'feishu', label: '飞书' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'notion', label: 'Notion' },
  { value: 'calendar', label: '日历' },
  { value: 'custom_http', label: '自定义 HTTP' },
];

const EXTERNAL_CAPABILITY_OPTIONS: Array<{ value: ExternalCapability; label: string }> = [
  { value: 'write', label: '写入' },
  { value: 'read', label: '读取' },
  { value: 'sync', label: '同步' },
  { value: 'notify', label: '通知' },
  { value: 'lookup', label: '查询' },
  { value: 'export', label: '导出' },
];

const EXTERNAL_SCOPE_OPTIONS: Array<{ value: ExternalScopeType; label: string }> = [
  { value: 'global', label: '全局' },
  { value: 'project', label: '项目' },
  { value: 'item_type', label: '事项类型' },
  { value: 'source_type', label: '来源类型' },
  { value: 'person', label: '人员' },
  { value: 'tag', label: '标签' },
];

const EXTERNAL_CONFLICT_OPTIONS: Array<{ value: ExternalConflictPolicy; label: string }> = [
  { value: 'ask', label: '冲突时询问' },
  { value: 'append', label: '总是追加' },
  { value: 'update', label: '匹配后更新' },
  { value: 'skip', label: '跳过' },
];

function ExternalProfilesSection({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const profilePresets = useQuery({ queryKey: ['external-profile-presets'], queryFn: () => api.externalProfilePresets() });
  const purposePresets = useQuery({ queryKey: ['external-purpose-presets'], queryFn: () => api.externalPurposePresets() });
  const profiles = useQuery({ queryKey: ['external-profiles'], queryFn: () => api.externalProfiles() });
  const bindings = useQuery({ queryKey: ['external-bindings'], queryFn: () => api.externalBindings() });

  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [profileName, setProfileName] = useState('飞书多维表格');
  const [presetKey, setPresetKey] = useState('feishu_bitable');
  const [providerKey, setProviderKey] = useState<ExternalProviderKey>('feishu');
  const [capability, setCapability] = useState<ExternalCapability>('write');
  const [authRef, setAuthRef] = useState('runtime_external');
  const [profilePriority, setProfilePriority] = useState('100');
  const [profileActive, setProfileActive] = useState(true);

  const [editingBindingId, setEditingBindingId] = useState<string | null>(null);
  const [purposeKey, setPurposeKey] = useState('item_write');
  const [bindingProfileId, setBindingProfileId] = useState('');
  const [scopeType, setScopeType] = useState<ExternalScopeType>('global');
  const [scopeValue, setScopeValue] = useState('');
  const [targetRef, setTargetRef] = useState('');
  const [formatKey, setFormatKey] = useState('feishu_bitable_item_v1');
  const [fieldMapping, setFieldMapping] = useState(objectText(FEISHU_WRITE_FIELD_MAPPING));
  const [valueMapping, setValueMapping] = useState(objectText({}));
  const [instructions, setInstructions] = useState('');
  const [conflictPolicy, setConflictPolicy] = useState<ExternalConflictPolicy>('append');
  const [dryRun, setDryRun] = useState(false);
  const [bindingPriority, setBindingPriority] = useState('100');
  const [bindingActive, setBindingActive] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!bindingProfileId && profiles.data?.[0]) setBindingProfileId(profiles.data[0].id);
  }, [bindingProfileId, profiles.data]);

  const saveProfile = useMutation({
    mutationFn: ({ id, payload }: { id: string | null; payload: ExternalProfilePayload }) =>
      id ? api.patchExternalProfile(session.csrf_token, id, payload) : api.createExternalProfile(session.csrf_token, payload),
    onSuccess: () => {
      resetProfileForm();
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['external-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['external-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const removeProfile = useMutation({
    mutationFn: (profileId: string) => api.deleteExternalProfile(session.csrf_token, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['external-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const patchProfile = useMutation({
    mutationFn: ({ profileId, payload }: { profileId: string; payload: Partial<ExternalProfilePayload> }) =>
      api.patchExternalProfile(session.csrf_token, profileId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['external-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['external-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const saveBinding = useMutation({
    mutationFn: ({ id, payload }: { id: string | null; payload: ExternalBindingPayload }) =>
      id ? api.patchExternalBinding(session.csrf_token, id, payload) : api.createExternalBinding(session.csrf_token, payload),
    onSuccess: () => {
      resetBindingForm();
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['external-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const removeBinding = useMutation({
    mutationFn: (bindingId: string) => api.deleteExternalBinding(session.csrf_token, bindingId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['external-bindings'] }),
    onError: (err) => setError(err.message),
  });

  const patchBinding = useMutation({
    mutationFn: ({ bindingId, payload }: { bindingId: string; payload: Partial<ExternalBindingPayload> }) =>
      api.patchExternalBinding(session.csrf_token, bindingId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['external-bindings'] }),
    onError: (err) => setError(err.message),
  });

  function applyProfilePreset(key: string) {
    const preset = profilePresets.data?.find((row) => row.preset_key === key);
    if (!preset) return;
    setPresetKey(preset.preset_key);
    setProfileName(preset.label);
    setProviderKey(preset.provider_key);
    setCapability(preset.capability);
    setAuthRef(preset.auth_ref ?? 'runtime_external');
    setFormatKey(preset.default_format_key);
    setFieldMapping(objectText(preset.default_field_mapping));
  }

  function resetProfileForm() {
    setEditingProfileId(null);
    setProfileName('飞书多维表格');
    setPresetKey('feishu_bitable');
    setProviderKey('feishu');
    setCapability('write');
    setAuthRef('runtime_external');
    setProfilePriority('100');
    setProfileActive(true);
  }

  function editProfile(profile: ExternalProfile) {
    setEditingProfileId(profile.id);
    setProfileName(profile.name);
    setPresetKey(profile.preset_key ?? '');
    setProviderKey(profile.provider_key);
    setCapability(profile.capability);
    setAuthRef(profile.auth_ref ?? '');
    setProfilePriority(String(profile.priority));
    setProfileActive(profile.active);
  }

  function submitProfile(event: FormEvent) {
    event.preventDefault();
    saveProfile.mutate({
      id: editingProfileId,
      payload: {
        name: profileName.trim(),
        provider_key: providerKey,
        preset_key: presetKey.trim() || null,
        capability,
        auth_ref: authRef.trim() || null,
        active: profileActive,
        priority: Number(profilePriority) || 100,
      },
    });
  }

  function resetBindingForm() {
    const preset = profilePresets.data?.find((row) => row.preset_key === 'feishu_bitable');
    setEditingBindingId(null);
    setPurposeKey('item_write');
    setBindingProfileId(profiles.data?.[0]?.id ?? '');
    setScopeType('global');
    setScopeValue('');
    setTargetRef('');
    setFormatKey(preset?.default_format_key ?? 'feishu_bitable_item_v1');
    setFieldMapping(objectText(preset?.default_field_mapping ?? FEISHU_WRITE_FIELD_MAPPING));
    setValueMapping(objectText({}));
    setInstructions('');
    setConflictPolicy('append');
    setDryRun(false);
    setBindingPriority('100');
    setBindingActive(true);
  }

  function editBinding(binding: ExternalBinding) {
    setEditingBindingId(binding.id);
    setPurposeKey(binding.purpose_key);
    setBindingProfileId(binding.profile_id);
    setScopeType(binding.scope_type);
    setScopeValue(binding.scope_value ?? '');
    setTargetRef(binding.target_ref);
    setFormatKey(binding.format_key);
    setFieldMapping(objectText(binding.field_mapping));
    setValueMapping(objectText(binding.value_mapping));
    setInstructions(binding.instructions ?? '');
    setConflictPolicy(binding.conflict_policy);
    setDryRun(binding.dry_run);
    setBindingPriority(String(binding.priority));
    setBindingActive(binding.active);
  }

  function submitBinding(event: FormEvent) {
    event.preventDefault();
    if (!bindingProfileId) {
      setError('请先选择一个外部 Profile');
      return;
    }
    try {
      saveBinding.mutate({
        id: editingBindingId,
        payload: {
          profile_id: bindingProfileId,
          purpose_key: purposeKey.trim(),
          scope_type: scopeType,
          scope_value: scopeType === 'global' ? null : scopeValue.trim() || null,
          target_ref: targetRef.trim(),
          format_key: formatKey.trim(),
          field_mapping: parseObject(fieldMapping, '字段映射'),
          value_mapping: parseObject(valueMapping, '值映射'),
          instructions: instructions.trim() || null,
          conflict_policy: conflictPolicy,
          dry_run: dryRun,
          active: bindingActive,
          priority: Number(bindingPriority) || 100,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '外部绑定 JSON 无效');
    }
  }

  const purposeOptions = purposePresets.data ?? [];

  return (
    <>
      <section className="settings-card">
        <h2>{editingProfileId ? '编辑外部 Profile' : '新增外部 Profile'}</h2>
        <p className="hint">Profile 描述外部系统和能力；具体表格、日历、Webhook、格式和字段映射放在用途绑定里。</p>
        <form className="form-grid external-profile-form" onSubmit={submitProfile}>
          <select value={presetKey} onChange={(event) => event.target.value ? applyProfilePreset(event.target.value) : setPresetKey('')}>
            <option value="">自定义 Profile</option>
            {profilePresets.data?.map((preset) => (
              <option key={preset.preset_key} value={preset.preset_key}>{preset.label}</option>
            ))}
          </select>
          <input value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="Profile 名称" />
          <select value={providerKey} onChange={(event) => setProviderKey(event.target.value as ExternalProviderKey)}>
            {EXTERNAL_PROVIDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <select value={capability} onChange={(event) => setCapability(event.target.value as ExternalCapability)}>
            {EXTERNAL_CAPABILITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input value={authRef} onChange={(event) => setAuthRef(event.target.value)} placeholder="凭据引用，如 runtime_external / env:KEY / none" />
          <input type="number" min="0" max="10000" value={profilePriority} onChange={(event) => setProfilePriority(event.target.value)} placeholder="优先级" />
          <label className="toggle-line compact">
            <input type="checkbox" checked={profileActive} onChange={(event) => setProfileActive(event.target.checked)} />
            启用
          </label>
          <div className="panel-actions">
            {editingProfileId && <button className="ghost sm" type="button" onClick={resetProfileForm}>取消编辑</button>}
            <button className="ghost sm" type="button" disabled={!presetKey} onClick={() => applyProfilePreset(presetKey)}>重载预设</button>
            <button className="primary" type="submit" disabled={saveProfile.isPending || !profileName.trim()}>
              {editingProfileId ? '保存 Profile' : '创建 Profile'}
            </button>
          </div>
        </form>
      </section>

      <section className="settings-card">
        <h2>{editingBindingId ? '编辑外部绑定' : '新增外部绑定'}</h2>
        <p className="hint">Binding 描述某个用途要写到哪里、按什么格式、字段如何映射，以及 Agent 必须遵守的说明。</p>
        <form className="form-grid external-profile-form" onSubmit={submitBinding}>
          <select value={purposeKey} onChange={(event) => setPurposeKey(event.target.value)}>
            {purposeOptions.map((purpose) => (
              <option key={purpose.purpose_key} value={purpose.purpose_key}>{purpose.label}</option>
            ))}
            {!purposeOptions.some((purpose) => purpose.purpose_key === purposeKey) && <option value={purposeKey}>{purposeKey}</option>}
          </select>
          <select value={bindingProfileId} onChange={(event) => setBindingProfileId(event.target.value)}>
            <option value="">选择外部 Profile</option>
            {profiles.data?.map((profile) => (
              <option key={profile.id} value={profile.id}>{profile.name} · {profile.provider_key}/{profile.capability}</option>
            ))}
          </select>
          <select value={scopeType} onChange={(event) => setScopeType(event.target.value as ExternalScopeType)}>
            {EXTERNAL_SCOPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input value={scopeValue} disabled={scopeType === 'global'} onChange={(event) => setScopeValue(event.target.value)} placeholder="范围值，global 留空" />
          <input value={targetRef} onChange={(event) => setTargetRef(event.target.value)} placeholder="目标引用：表链接、日历 ID、Webhook URL、数据库 ID" />
          <input value={formatKey} onChange={(event) => setFormatKey(event.target.value)} placeholder="格式键，如 feishu_bitable_item_v1" />
          <select value={conflictPolicy} onChange={(event) => setConflictPolicy(event.target.value as ExternalConflictPolicy)}>
            {EXTERNAL_CONFLICT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input type="number" min="0" max="10000" value={bindingPriority} onChange={(event) => setBindingPriority(event.target.value)} placeholder="优先级" />
          <textarea value={fieldMapping} rows={8} spellCheck={false} onChange={(event) => setFieldMapping(event.target.value)} />
          <textarea value={valueMapping} rows={6} spellCheck={false} onChange={(event) => setValueMapping(event.target.value)} />
          <textarea value={instructions} rows={4} onChange={(event) => setInstructions(event.target.value)} placeholder="给 Agent 的说明，如去重字段、冲突策略、哪些事项不要同步、是否只 dry-run" />
          <label className="toggle-line compact">
            <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
            Dry-run
          </label>
          <label className="toggle-line compact">
            <input type="checkbox" checked={bindingActive} onChange={(event) => setBindingActive(event.target.checked)} />
            启用
          </label>
          <div className="panel-actions">
            {editingBindingId && <button className="ghost sm" type="button" onClick={resetBindingForm}>取消编辑</button>}
            <button className="primary" type="submit" disabled={saveBinding.isPending || !purposeKey.trim() || !bindingProfileId || !targetRef.trim()}>
              {editingBindingId ? '保存绑定' : '创建绑定'}
            </button>
          </div>
        </form>
        {error && <p className="error-line">{error}</p>}
      </section>

      <section className="settings-card">
        <h2>已配置外部 Profile</h2>
        {profiles.isLoading && <p className="hint">加载中…</p>}
        {profiles.data && profiles.data.length === 0 && <p className="hint">尚未配置外部 Profile。</p>}
        <div className="settings-row-list">
          {profiles.data?.map((profile) => (
            <div key={profile.id} className={profile.active ? 'settings-row' : 'settings-row inactive'}>
              <div className="settings-row-info">
                <strong>{profile.name}{profile.active ? '' : '（已停用）'}</strong>
                <span>{profile.provider_key} · {profile.capability}</span>
                <span>{profile.auth_ref ?? '无凭据引用'} · priority {profile.priority}</span>
              </div>
              <div className="settings-row-controls">
                <span className={profile.active ? 'state-badge on' : 'state-badge warn'}>{profile.preset_key ?? 'custom'}</span>
                <button className="ghost sm" type="button" onClick={() => editProfile(profile)}>编辑</button>
                <button className="ghost sm" type="button" disabled={patchProfile.isPending} onClick={() => patchProfile.mutate({ profileId: profile.id, payload: { active: !profile.active } })}>
                  {profile.active ? '停用' : '启用'}
                </button>
                <button className="ghost sm danger-text" type="button" disabled={removeProfile.isPending} onClick={() => removeProfile.mutate(profile.id)}>删除</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="settings-card">
        <h2>外部用途绑定</h2>
        {bindings.isLoading && <p className="hint">加载中…</p>}
        {bindings.data && bindings.data.length === 0 && <p className="hint">尚未配置外部绑定；旧版写入目标会在迁移后作为 item_write 绑定出现。</p>}
        <div className="settings-row-list">
          {bindings.data?.map((binding) => (
            <div key={binding.id} className={binding.active ? 'settings-row' : 'settings-row inactive'}>
              <div className="settings-row-info">
                <strong>{purposeOptions.find((purpose) => purpose.purpose_key === binding.purpose_key)?.label ?? binding.purpose_key}{binding.active ? '' : '（已停用）'}</strong>
                <span>{binding.profile_name} · {binding.target_ref}</span>
                <span>{binding.format_key} · {EXTERNAL_SCOPE_OPTIONS.find((option) => option.value === binding.scope_type)?.label ?? binding.scope_type}{binding.scope_value ? `: ${binding.scope_value}` : ''}</span>
                {binding.last_error && <span>最近错误：{binding.last_error}</span>}
              </div>
              <div className="settings-row-controls">
                <span className={binding.active ? 'state-badge on' : 'state-badge warn'}>{binding.dry_run ? 'dry-run' : binding.conflict_policy}</span>
                <button className="ghost sm" type="button" onClick={() => editBinding(binding)}>编辑</button>
                <button className="ghost sm" type="button" disabled={patchBinding.isPending} onClick={() => patchBinding.mutate({ bindingId: binding.id, payload: { active: !binding.active } })}>
                  {binding.active ? '停用' : '启用'}
                </button>
                <button className="ghost sm danger-text" type="button" disabled={removeBinding.isPending} onClick={() => removeBinding.mutate(binding.id)}>删除</button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function LLMProfilesSection({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const profilePresets = useQuery({ queryKey: ['llm-profile-presets'], queryFn: () => api.llmProfilePresets() });
  const purposePresets = useQuery({ queryKey: ['llm-purpose-presets'], queryFn: () => api.llmPurposePresets() });
  const profiles = useQuery({ queryKey: ['llm-profiles'], queryFn: () => api.llmProfiles() });
  const bindings = useQuery({ queryKey: ['llm-bindings'], queryFn: () => api.llmBindings() });

  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [profileName, setProfileName] = useState('LiteLLM DeepSeek Flash');
  const [providerKey, setProviderKey] = useState<LLMProviderKey>('litellm');
  const [presetKey, setPresetKey] = useState('litellm_deepseek_flash');
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:14000/v1');
  const [modelName, setModelName] = useState('deepseek:deepseek-v4-flash');
  const [authRef, setAuthRef] = useState('intake_normalization_api_key');
  const [capabilities, setCapabilities] = useState(objectText(DEFAULT_LLM_CAPABILITIES));
  const [defaultParams, setDefaultParams] = useState(objectText(DEFAULT_LLM_PARAMS));
  const [privacyTier, setPrivacyTier] = useState<LLMPrivacyTier>('standard');
  const [profilePriority, setProfilePriority] = useState('100');
  const [profileActive, setProfileActive] = useState(true);

  const [editingBindingId, setEditingBindingId] = useState<string | null>(null);
  const [purposeKey, setPurposeKey] = useState('intake_normalization');
  const [scopeType, setScopeType] = useState<LLMScopeType>('global');
  const [scopeValue, setScopeValue] = useState('');
  const [bindingProfileId, setBindingProfileId] = useState('');
  const [overrideParams, setOverrideParams] = useState(objectText({ timeout_seconds: 3, min_confidence: 0.55 }));
  const [bindingInstructions, setBindingInstructions] = useState('');
  const [bindingPriority, setBindingPriority] = useState('100');
  const [bindingActive, setBindingActive] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!bindingProfileId && profiles.data?.[0]) setBindingProfileId(profiles.data[0].id);
  }, [bindingProfileId, profiles.data]);

  const saveProfile = useMutation({
    mutationFn: ({ id, payload }: { id: string | null; payload: LLMProfilePayload }) =>
      id ? api.patchLLMProfile(session.csrf_token, id, payload) : api.createLLMProfile(session.csrf_token, payload),
    onSuccess: () => {
      resetProfileForm();
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['llm-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['llm-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const removeProfile = useMutation({
    mutationFn: (profileId: string) => api.deleteLLMProfile(session.csrf_token, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['llm-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const patchProfile = useMutation({
    mutationFn: ({ profileId, payload }: { profileId: string; payload: Partial<LLMProfilePayload> }) =>
      api.patchLLMProfile(session.csrf_token, profileId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-profiles'] });
      queryClient.invalidateQueries({ queryKey: ['llm-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const saveBinding = useMutation({
    mutationFn: ({ id, payload }: { id: string | null; payload: LLMBindingPayload }) =>
      id ? api.patchLLMBinding(session.csrf_token, id, payload) : api.createLLMBinding(session.csrf_token, payload),
    onSuccess: () => {
      resetBindingForm();
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['llm-bindings'] });
    },
    onError: (err) => setError(err.message),
  });

  const removeBinding = useMutation({
    mutationFn: (bindingId: string) => api.deleteLLMBinding(session.csrf_token, bindingId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llm-bindings'] }),
    onError: (err) => setError(err.message),
  });

  const patchBinding = useMutation({
    mutationFn: ({ bindingId, payload }: { bindingId: string; payload: Partial<LLMBindingPayload> }) =>
      api.patchLLMBinding(session.csrf_token, bindingId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llm-bindings'] }),
    onError: (err) => setError(err.message),
  });

  function applyProfilePreset(key: string) {
    const preset = profilePresets.data?.find((row) => row.preset_key === key);
    if (!preset) return;
    setPresetKey(preset.preset_key);
    setProfileName(preset.label);
    setProviderKey(preset.provider_key);
    setBaseUrl(preset.base_url ?? '');
    setModelName(preset.model_name);
    setAuthRef(preset.auth_ref ?? '');
    setCapabilities(objectText(preset.capabilities));
    setDefaultParams(objectText(preset.default_params));
    setPrivacyTier(preset.privacy_tier);
  }

  function resetProfileForm() {
    setEditingProfileId(null);
    setProfileName('LiteLLM DeepSeek Flash');
    setProviderKey('litellm');
    setPresetKey('litellm_deepseek_flash');
    setBaseUrl('http://127.0.0.1:14000/v1');
    setModelName('deepseek:deepseek-v4-flash');
    setAuthRef('intake_normalization_api_key');
    setCapabilities(objectText(DEFAULT_LLM_CAPABILITIES));
    setDefaultParams(objectText(DEFAULT_LLM_PARAMS));
    setPrivacyTier('standard');
    setProfilePriority('100');
    setProfileActive(true);
  }

  function editProfile(profile: LLMProfile) {
    setEditingProfileId(profile.id);
    setProfileName(profile.name);
    setProviderKey(profile.provider_key);
    setPresetKey(profile.preset_key ?? '');
    setBaseUrl(profile.base_url ?? '');
    setModelName(profile.model_name);
    setAuthRef(profile.auth_ref ?? '');
    setCapabilities(objectText(profile.capabilities));
    setDefaultParams(objectText(profile.default_params));
    setPrivacyTier(profile.privacy_tier);
    setProfilePriority(String(profile.priority));
    setProfileActive(profile.active);
  }

  function submitProfile(event: FormEvent) {
    event.preventDefault();
    try {
      saveProfile.mutate({
        id: editingProfileId,
        payload: {
          name: profileName.trim(),
          provider_key: providerKey,
          preset_key: presetKey.trim() || null,
          base_url: baseUrl.trim() || null,
          model_name: modelName.trim(),
          auth_ref: authRef.trim() || null,
          capabilities: parseObject(capabilities, '能力配置'),
          default_params: parseObject(defaultParams, '默认参数'),
          privacy_tier: privacyTier,
          active: profileActive,
          priority: Number(profilePriority) || 100,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '模型配置 JSON 无效');
    }
  }

  function resetBindingForm() {
    setEditingBindingId(null);
    setPurposeKey('intake_normalization');
    setScopeType('global');
    setScopeValue('');
    setBindingProfileId(profiles.data?.[0]?.id ?? '');
    setOverrideParams(objectText({ timeout_seconds: 3, min_confidence: 0.55 }));
    setBindingInstructions('');
    setBindingPriority('100');
    setBindingActive(true);
  }

  function editBinding(binding: LLMBinding) {
    setEditingBindingId(binding.id);
    setPurposeKey(binding.purpose_key);
    setScopeType(binding.scope_type);
    setScopeValue(binding.scope_value ?? '');
    setBindingProfileId(binding.profile_id);
    setOverrideParams(objectText(binding.override_params));
    setBindingInstructions(binding.instructions ?? '');
    setBindingPriority(String(binding.priority));
    setBindingActive(binding.active);
  }

  function submitBinding(event: FormEvent) {
    event.preventDefault();
    if (!bindingProfileId) {
      setError('请先选择一个模型 Profile');
      return;
    }
    try {
      saveBinding.mutate({
        id: editingBindingId,
        payload: {
          purpose_key: purposeKey.trim(),
          scope_type: scopeType,
          scope_value: scopeType === 'global' ? null : scopeValue.trim() || null,
          profile_id: bindingProfileId,
          override_params: parseObject(overrideParams, '覆盖参数'),
          instructions: bindingInstructions.trim() || null,
          active: bindingActive,
          priority: Number(bindingPriority) || 100,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '绑定配置 JSON 无效');
    }
  }

  const purposeOptions = purposePresets.data ?? [];

  return (
    <>
      <section className="settings-card">
        <h2>{editingProfileId ? '编辑模型 Profile' : '新增模型 Profile'}</h2>
        <p className="hint">模型选择按用途绑定；预设只是默认值，base URL、模型名、参数、能力和凭据引用都可覆盖。</p>
        <form className="form-grid llm-profile-form" onSubmit={submitProfile}>
          <select value={presetKey} onChange={(event) => event.target.value ? applyProfilePreset(event.target.value) : setPresetKey('')}>
            <option value="">自定义 Profile</option>
            {profilePresets.data?.map((preset) => (
              <option key={preset.preset_key} value={preset.preset_key}>{preset.label}</option>
            ))}
          </select>
          <input value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="Profile 名称" />
          <select value={providerKey} onChange={(event) => setProviderKey(event.target.value as LLMProviderKey)}>
            {LLM_PROVIDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder="模型名，如 deepseek:deepseek-v4-flash" />
          <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="Base URL，如 http://127.0.0.1:14000/v1" />
          <input value={authRef} onChange={(event) => setAuthRef(event.target.value)} placeholder="凭据引用，如 intake_normalization_api_key / env:KEY / none" />
          <select value={privacyTier} onChange={(event) => setPrivacyTier(event.target.value as LLMPrivacyTier)}>
            {LLM_PRIVACY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input type="number" min="0" max="10000" value={profilePriority} onChange={(event) => setProfilePriority(event.target.value)} placeholder="优先级" />
          <textarea value={capabilities} rows={7} spellCheck={false} onChange={(event) => setCapabilities(event.target.value)} />
          <textarea value={defaultParams} rows={7} spellCheck={false} onChange={(event) => setDefaultParams(event.target.value)} />
          <label className="toggle-line compact">
            <input type="checkbox" checked={profileActive} onChange={(event) => setProfileActive(event.target.checked)} />
            启用
          </label>
          <div className="panel-actions">
            {editingProfileId && <button className="ghost sm" type="button" onClick={resetProfileForm}>取消编辑</button>}
            <button className="ghost sm" type="button" disabled={!presetKey} onClick={() => applyProfilePreset(presetKey)}>重载预设</button>
            <button className="primary" type="submit" disabled={saveProfile.isPending || !profileName.trim() || !modelName.trim()}>
              {editingProfileId ? '保存模型' : '创建模型'}
            </button>
          </div>
        </form>
      </section>

      <section className="settings-card">
        <h2>{editingBindingId ? '编辑用途绑定' : '新增用途绑定'}</h2>
        <p className="hint">Agent 和服务端调用 LLM 前按用途读取绑定，例如快速录入、提议抽取、今日简报或外部格式化。</p>
        <form className="form-grid llm-profile-form" onSubmit={submitBinding}>
          <select value={purposeKey} onChange={(event) => setPurposeKey(event.target.value)}>
            {purposeOptions.map((purpose) => (
              <option key={purpose.purpose_key} value={purpose.purpose_key}>{purpose.label}</option>
            ))}
            {!purposeOptions.some((purpose) => purpose.purpose_key === purposeKey) && <option value={purposeKey}>{purposeKey}</option>}
          </select>
          <select value={bindingProfileId} onChange={(event) => setBindingProfileId(event.target.value)}>
            <option value="">选择模型 Profile</option>
            {profiles.data?.map((profile) => (
              <option key={profile.id} value={profile.id}>{profile.name} · {profile.model_name}</option>
            ))}
          </select>
          <select value={scopeType} onChange={(event) => setScopeType(event.target.value as LLMScopeType)}>
            {LLM_SCOPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input value={scopeValue} disabled={scopeType === 'global'} onChange={(event) => setScopeValue(event.target.value)} placeholder="范围值，global 留空" />
          <input type="number" min="0" max="10000" value={bindingPriority} onChange={(event) => setBindingPriority(event.target.value)} placeholder="优先级" />
          <textarea value={overrideParams} rows={7} spellCheck={false} onChange={(event) => setOverrideParams(event.target.value)} />
          <textarea value={bindingInstructions} rows={4} onChange={(event) => setBindingInstructions(event.target.value)} placeholder="给 Agent 的补充说明，如只做 JSON 抽取、失败进入人工确认、不得直接写入正式事项等" />
          <label className="toggle-line compact">
            <input type="checkbox" checked={bindingActive} onChange={(event) => setBindingActive(event.target.checked)} />
            启用
          </label>
          <div className="panel-actions">
            {editingBindingId && <button className="ghost sm" type="button" onClick={resetBindingForm}>取消编辑</button>}
            <button className="primary" type="submit" disabled={saveBinding.isPending || !purposeKey.trim() || !bindingProfileId}>
              {editingBindingId ? '保存绑定' : '创建绑定'}
            </button>
          </div>
        </form>
        {error && <p className="error-line">{error}</p>}
      </section>

      <section className="settings-card">
        <h2>已配置模型</h2>
        {profiles.isLoading && <p className="hint">加载中…</p>}
        {profiles.data && profiles.data.length === 0 && <p className="hint">尚未配置模型 Profile。</p>}
        <div className="settings-row-list">
          {profiles.data?.map((profile) => (
            <div key={profile.id} className={profile.active ? 'settings-row' : 'settings-row inactive'}>
              <div className="settings-row-info">
                <strong>{profile.name}{profile.active ? '' : '（已停用）'}</strong>
                <span>{profile.model_name} · {profile.base_url ?? '无 base URL'}</span>
                <span>{profile.auth_ref ?? '无凭据引用'} · priority {profile.priority}</span>
              </div>
              <div className="settings-row-controls">
                <span className={profile.active ? 'state-badge on' : 'state-badge warn'}>{profile.provider_key}</span>
                <button className="ghost sm" type="button" onClick={() => editProfile(profile)}>编辑</button>
                <button className="ghost sm" type="button" disabled={patchProfile.isPending} onClick={() => patchProfile.mutate({ profileId: profile.id, payload: { active: !profile.active } })}>
                  {profile.active ? '停用' : '启用'}
                </button>
                <button className="ghost sm danger-text" type="button" disabled={removeProfile.isPending} onClick={() => removeProfile.mutate(profile.id)}>删除</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="settings-card">
        <h2>用途绑定</h2>
        {bindings.isLoading && <p className="hint">加载中…</p>}
        {bindings.data && bindings.data.length === 0 && <p className="hint">尚未配置 LLM 用途绑定；未配置时录入归一化继续使用服务端 env fallback。</p>}
        <div className="settings-row-list">
          {bindings.data?.map((binding) => (
            <div key={binding.id} className={binding.active ? 'settings-row' : 'settings-row inactive'}>
              <div className="settings-row-info">
                <strong>{purposeOptions.find((purpose) => purpose.purpose_key === binding.purpose_key)?.label ?? binding.purpose_key}{binding.active ? '' : '（已停用）'}</strong>
                <span>{binding.profile_name} · {binding.model_name}</span>
                <span>{LLM_SCOPE_OPTIONS.find((option) => option.value === binding.scope_type)?.label ?? binding.scope_type}{binding.scope_value ? `: ${binding.scope_value}` : ''} · priority {binding.priority}</span>
              </div>
              <div className="settings-row-controls">
                <span className={binding.active ? 'state-badge on' : 'state-badge warn'}>{binding.provider_key}</span>
                <button className="ghost sm" type="button" onClick={() => editBinding(binding)}>编辑</button>
                <button className="ghost sm" type="button" disabled={patchBinding.isPending} onClick={() => patchBinding.mutate({ bindingId: binding.id, payload: { active: !binding.active } })}>
                  {binding.active ? '停用' : '启用'}
                </button>
                <button className="ghost sm danger-text" type="button" disabled={removeBinding.isPending} onClick={() => removeBinding.mutate(binding.id)}>删除</button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function WriteTargetsSection({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const presets = useQuery({ queryKey: ['write-target-presets'], queryFn: () => api.writeTargetPresets() });
  const targets = useQuery({ queryKey: ['write-targets'], queryFn: () => api.writeTargets() });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState('飞书多维表格');
  const [targetType, setTargetType] = useState<WriteTargetType>('feishu_bitable');
  const [targetUrl, setTargetUrl] = useState('');
  const [formatKey, setFormatKey] = useState<WriteTargetFormat>('feishu_bitable_item_v1');
  const [fieldMapping, setFieldMapping] = useState(mappingText(FEISHU_WRITE_FIELD_MAPPING));
  const [instructions, setInstructions] = useState('');
  const [active, setActive] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const saveTarget = useMutation({
    mutationFn: ({ id, payload }: { id: string | null; payload: WriteTargetPayload }) =>
      id ? api.patchWriteTarget(session.csrf_token, id, payload) : api.createWriteTarget(session.csrf_token, payload),
    onSuccess: () => {
      resetForm();
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['write-targets'] });
    },
    onError: (err) => setError(err.message),
  });
  const removeTarget = useMutation({
    mutationFn: (targetId: string) => api.deleteWriteTarget(session.csrf_token, targetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['write-targets'] }),
    onError: (err) => setError(err.message),
  });
  const patchTarget = useMutation({
    mutationFn: ({ targetId, payload }: { targetId: string; payload: Partial<WriteTargetPayload> }) =>
      api.patchWriteTarget(session.csrf_token, targetId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['write-targets'] }),
    onError: (err) => setError(err.message),
  });

  function presetFor(type: WriteTargetType) {
    return presets.data?.find((preset) => preset.target_type === type);
  }

  function applyPreset(type: WriteTargetType) {
    const preset = presetFor(type);
    setTargetType(type);
    setFormatKey((preset?.format_key ?? (type === 'feishu_bitable' ? 'feishu_bitable_item_v1' : 'custom_json_v1')) as WriteTargetFormat);
    setFieldMapping(mappingText(preset?.field_mapping ?? (type === 'feishu_bitable' ? FEISHU_WRITE_FIELD_MAPPING : {})));
    if (!name.trim() || WRITE_TARGET_TYPE_OPTIONS.some((option) => option.label === name)) {
      setName(preset?.label ?? WRITE_TARGET_TYPE_OPTIONS.find((option) => option.value === type)?.label ?? '写入目标');
    }
  }

  function resetForm() {
    setEditingId(null);
    setName('飞书多维表格');
    setTargetType('feishu_bitable');
    setTargetUrl('');
    setFormatKey('feishu_bitable_item_v1');
    setFieldMapping(mappingText(presetFor('feishu_bitable')?.field_mapping ?? FEISHU_WRITE_FIELD_MAPPING));
    setInstructions('');
    setActive(true);
  }

  function editTarget(target: WriteTarget) {
    setEditingId(target.id);
    setName(target.name);
    setTargetType(target.target_type);
    setTargetUrl(target.target_url);
    setFormatKey(target.format_key);
    setFieldMapping(mappingText(target.field_mapping));
    setInstructions(target.instructions ?? '');
    setActive(target.active);
  }

  function submitTarget(event: FormEvent) {
    event.preventDefault();
    try {
      const mapping = parseMapping(fieldMapping);
      saveTarget.mutate({
        id: editingId,
        payload: {
          name: name.trim(),
          target_type: targetType,
          target_url: targetUrl.trim(),
          format_key: formatKey,
          field_mapping: mapping,
          instructions: instructions.trim() || null,
          active,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '字段映射 JSON 无效');
    }
  }

  return (
    <>
      <section className="settings-card">
        <h2>{editingId ? '编辑写入目标' : '新增写入目标'}</h2>
        <p className="hint">飞书多维表格是内置预设；链接、格式键、字段映射和补充说明均可覆盖，供 Agent 或自动化写入时读取。</p>
        <form className="form-grid write-target-form" onSubmit={submitTarget}>
          <select value={targetType} onChange={(event) => applyPreset(event.target.value as WriteTargetType)}>
            {WRITE_TARGET_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="目标名称" />
          <input
            value={targetUrl}
            onChange={(event) => setTargetUrl(event.target.value)}
            placeholder={targetType === 'feishu_bitable' ? '飞书多维表格链接' : '目标链接或执行端点'}
          />
          <select value={formatKey} onChange={(event) => setFormatKey(event.target.value as WriteTargetFormat)}>
            {WRITE_TARGET_FORMAT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <textarea
            value={fieldMapping}
            rows={10}
            spellCheck={false}
            onChange={(event) => setFieldMapping(event.target.value)}
            placeholder='{"title":"事项名称","scope":"范围"}'
          />
          <textarea
            value={instructions}
            rows={4}
            onChange={(event) => setInstructions(event.target.value)}
            placeholder="给 Agent 的补充说明，如只同步 active 项、状态枚举如何映射、是否追加来源链接等"
          />
          <label className="toggle-line compact">
            <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
            启用
          </label>
          <div className="panel-actions">
            {editingId && <button className="ghost sm" type="button" onClick={resetForm}>取消编辑</button>}
            <button className="ghost sm" type="button" onClick={() => applyPreset(targetType)}>重载预设字段</button>
            <button className="primary" type="submit" disabled={saveTarget.isPending || !name.trim() || !targetUrl.trim()}>
              {editingId ? '保存目标' : '创建目标'}
            </button>
          </div>
        </form>
        {error && <p className="error-line">{error}</p>}
      </section>

      <section className="settings-card">
        <h2>已配置写入目标</h2>
        {targets.isLoading && <p className="hint">加载中…</p>}
        {targets.data && targets.data.length === 0 && <p className="hint">尚未配置写入目标。</p>}
        <div className="settings-row-list">
          {targets.data?.map((target) => (
            <div key={target.id} className={target.active ? 'settings-row' : 'settings-row inactive'}>
              <div className="settings-row-info">
                <strong>{target.name}{target.active ? '' : '（已停用）'}</strong>
                <span>{target.target_url}</span>
                <span>{WRITE_TARGET_FORMAT_OPTIONS.find((option) => option.value === target.format_key)?.label ?? target.format_key} · {Object.keys(target.field_mapping).length} 个字段映射</span>
              </div>
              <div className="settings-row-controls">
                <span className={target.active ? 'state-badge on' : 'state-badge warn'}>
                  {WRITE_TARGET_TYPE_OPTIONS.find((option) => option.value === target.target_type)?.label ?? target.target_type}
                </span>
                <button className="ghost sm" type="button" onClick={() => editTarget(target)}>编辑</button>
                <button className="ghost sm" type="button" disabled={patchTarget.isPending} onClick={() => patchTarget.mutate({ targetId: target.id, payload: { active: !target.active } })}>
                  {target.active ? '停用' : '启用'}
                </button>
                <button className="ghost sm danger-text" type="button" disabled={removeTarget.isPending} onClick={() => removeTarget.mutate(target.id)}>
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
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
