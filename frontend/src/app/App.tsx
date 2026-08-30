import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bell,
  BriefcaseBusiness,
  CalendarDays,
  CircleAlert,
  ClipboardCheck,
  FolderKanban,
  Home,
  Inbox,
  LogIn,
  LogOut,
  Plus,
  Search,
  Settings,
  Tag,
  User,
} from 'lucide-react';
import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, api, Item, ReminderDelivery, Scope, Session } from '../api/client';
import { FocusBar } from '../components/FocusControls';
import { stashViewHandoff } from '../components/SavedViews';
import { QuickAddDialog } from '../components/QuickAddDialog';
import { ReminderDiagnosticsDialog } from '../components/ReminderDiagnosticsDialog';
import { SearchDialog } from '../components/SearchDialog';
import { ShortcutHelpDialog } from '../components/ShortcutHelpDialog';
import { formatScheduleTime, setAppTimezone } from '../lib/dates';
import { APP_NAME, APP_SHORT_NAME, BRAND_MARK } from '../lib/branding';
import { snoozeLabel, snoozeWakeAt } from '../lib/reminderPreview';
import { UndoProvider } from '../hooks/useUndo';
import { CalendarPage } from '../pages/CalendarPage';
import { PersonalItemsPage } from '../pages/PersonalItemsPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { ReviewPage } from '../pages/ReviewPage';
import { InboxPage } from '../pages/InboxPage';
import { TodayPage } from '../pages/TodayPage';
import { SettingsPage } from '../pages/SettingsPage';
import { TagsPage } from '../pages/TagsPage';
import { WorkItemsPage } from '../pages/WorkItemsPage';

type Page = 'today' | 'inbox' | 'work' | 'personal' | 'projects' | 'calendar' | 'tags' | 'settings' | 'review';

const pages: Page[] = ['today', 'inbox', 'work', 'personal', 'projects', 'calendar', 'tags', 'settings', 'review'];

type NavGroup = '工作台' | '事务' | '工具';

const navItems: Array<{ page: Page; label: string; icon: typeof Home; group: NavGroup }> = [
  { page: 'today', label: '今日', icon: Home, group: '工作台' },
  { page: 'inbox', label: '收集箱', icon: Inbox, group: '工作台' },
  { page: 'work', label: '工作事项', icon: BriefcaseBusiness, group: '事务' },
  { page: 'personal', label: '个人事项', icon: User, group: '事务' },
  { page: 'projects', label: '项目跟进', icon: FolderKanban, group: '事务' },
  { page: 'calendar', label: '日程提醒', icon: CalendarDays, group: '工具' },
  { page: 'tags', label: '标签', icon: Tag, group: '工具' },
  { page: 'settings', label: '设置', icon: Settings, group: '工具' },
];

const NAV_GROUPS: NavGroup[] = ['工作台', '事务', '工具'];
const reviewNavItem = { page: 'review' as Page, label: '复盘', icon: ClipboardCheck, group: '工具' as NavGroup };

function pageFromHash(): Page {
  const hash = window.location.hash.replace(/^#\/?/, '');
  return pages.includes(hash as Page) ? (hash as Page) : 'today';
}

function navigate(page: Page) {
  window.location.hash = `/${page}`;
}

export function App() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState<Page>(pageFromHash);
  const [apiError, setApiError] = useState<ApiError | null>(null);
  const session = useQuery({
    queryKey: ['session'],
    queryFn: api.session,
    retry: 2,
    retryDelay: (attempt) => Math.min(250 * 2 ** attempt, 1000),
  });

  useEffect(() => {
    const onApiError = (event: Event) => {
      const error = (event as CustomEvent<ApiError>).detail;
      setApiError(error);
    };
    const onSessionRefreshed = (event: Event) => {
      const nextSession = (event as CustomEvent<Session>).detail;
      queryClient.setQueryData(['session'], nextSession);
      setApiError(null);
    };
    const onAuthExpired = () => {
      queryClient.removeQueries({ queryKey: ['session'] });
    };
    window.addEventListener('pa-api-error', onApiError);
    window.addEventListener('pa-session-refreshed', onSessionRefreshed);
    window.addEventListener('pa-auth-expired', onAuthExpired);
    return () => {
      window.removeEventListener('pa-api-error', onApiError);
      window.removeEventListener('pa-session-refreshed', onSessionRefreshed);
      window.removeEventListener('pa-auth-expired', onAuthExpired);
    };
  }, [queryClient]);

  useEffect(() => {
    function onHashChange() {
      setPage(pageFromHash());
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    setAppTimezone(session.data?.timezone ?? null);
  }, [session.data?.timezone]);

  if (session.isLoading) return <div className="boot">Loading</div>;
  if (session.isError || !session.data) return <Login />;

  return (
    <>
      {apiError && (
        <div className="error-line" role="alert">
          {apiError.code === 'CSRF_REQUIRED'
            ? '登录状态已失效，请重新登录后重试。'
            : apiError.message}
          <button className="ghost sm" type="button" onClick={() => setApiError(null)}>
            关闭
          </button>
        </div>
      )}
      <UndoProvider>
        <Shell page={page} onNavigate={navigate} session={session.data}>
          {page === 'today' && <TodayPage session={session.data} />}
          {page === 'inbox' && <InboxPage session={session.data} />}
          {page === 'work' && <WorkItemsPage session={session.data} />}
          {page === 'personal' && <PersonalItemsPage session={session.data} />}
          {page === 'projects' && <ProjectsPage session={session.data} />}
          {page === 'calendar' && <CalendarPage session={session.data} />}
          {page === 'tags' && <TagsPage session={session.data} />}
          {page === 'settings' && <SettingsPage session={session.data} />}
          {page === 'review' && <ReviewGate session={session.data} />}
        </Shell>
      </UndoProvider>
    </>
  );
}

function ReviewGate({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const prefs = useQuery({ queryKey: ['preferences'], queryFn: api.preferences });
  const enable = useMutation({
    mutationFn: () => api.patchPreferences(session.csrf_token, { weekly_review_enabled: true }),
    onSuccess: (data) => queryClient.setQueryData(['preferences'], data),
  });
  if (prefs.data?.weekly_review_enabled) return <ReviewPage session={session} />;
  return (
    <div className="page">
      <header className="page-header">
        <h1>周复盘</h1>
        <p>周期回顾：清理逾期遗留、跟进协作事项、梳理项目下一步动作。该功能默认关闭。</p>
      </header>
      <div className="today-grid">
        <section className="today-card">
          <h2>
            <ClipboardCheck size={16} /> 功能未开启
          </h2>
          <div className="today-list">
            <p className="empty">开启后，左侧导航将显示「复盘」入口，可随时在设置中关闭。</p>
            <button className="primary" type="button" disabled={enable.isPending} onClick={() => enable.mutate()}>
              <ClipboardCheck size={15} /> 开启周复盘
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

function Login() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const login = useMutation({
    mutationFn: () => api.login(username, password),
    onSuccess: (session) => queryClient.setQueryData(['session'], session),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }

  return (
    <main className="login-view">
      <form className="login-panel" onSubmit={submit}>
        <div>
          <p className="eyebrow">{APP_NAME}</p>
          <h1>个人事务管理</h1>
        </div>
        <label>
          用户名
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoFocus />
        </label>
        <label>
          密码
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {login.isError && <p className="error-line">{String(login.error.message)}</p>}
        <button className="primary" type="submit" disabled={!username || !password || login.isPending}>
          <LogIn size={16} /> 登录
        </button>
      </form>
    </main>
  );
}

function Shell({
  children,
  page,
  onNavigate,
  session,
}: {
  children: ReactNode;
  page: Page;
  onNavigate: (page: Page) => void;
  session: Session;
}) {
  const health = useQuery({ queryKey: ['reminder-health'], queryFn: api.reminderHealth, refetchInterval: 60000 });
  const hasReminderIssue = health.data && (health.data.retry_count > 0 || health.data.dead_count > 0);
  const queryClient = useQueryClient();
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [shortcutHelpOpen, setShortcutHelpOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [diagOpen, setDiagOpen] = useState(false);
  const prefs = useQuery({ queryKey: ['preferences'], queryFn: api.preferences });
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });
  const allTags = useQuery({ queryKey: ['tags'], queryFn: api.tags });
  const inboxCount = useMemo(
    () =>
      [...(workItems.data ?? []), ...(personalItems.data ?? [])].filter((item) => item.status === 'inbox' && !item.archived_at).length,
    [workItems.data, personalItems.data],
  );
  const pinnedTags = useMemo(() => (allTags.data ?? []).filter((tag) => tag.pinned), [allTags.data]);
  const savedViews = useQuery({ queryKey: ['saved-views'], queryFn: api.savedViews });
  const deleteView = useMutation({
    mutationFn: (viewId: string) => api.deleteSavedView(session.csrf_token, viewId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['saved-views'] }),
  });
  const desktopNotifications = prefs.data?.desktop_notifications ?? false;

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setQuickAddOpen((open) => !open);
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'p') {
        event.preventDefault();
        setSearchOpen((open) => !open);
        return;
      }
      if (!event.metaKey && !event.ctrlKey && !event.altKey && event.key === '?') {
        const target = event.target as HTMLElement | null;
        if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
        if (target?.isContentEditable) return;
        event.preventDefault();
        setShortcutHelpOpen((open) => !open);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  function openSearchItem(item: Item) {
    window.sessionStorage.setItem('pa-open-item', item.id);
    onNavigate(item.scope === 'work' ? 'work' : 'personal');
    setSearchOpen(false);
  }

  const logout = useMutation({
    mutationFn: () => api.logout(session.csrf_token),
    onSettled: () => {
      queryClient.clear();
      window.location.hash = '/today';
      window.location.reload();
    },
  });

  const quickAddScope: Scope = page === 'personal' ? 'personal' : 'work';
  const visibleNavItems = (prefs.data?.weekly_review_enabled ?? false) ? [...navItems, reviewNavItem] : navItems;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">{BRAND_MARK}</span>
          <span>{APP_SHORT_NAME}</span>
        </div>
        <button className="primary sidebar-quick-add" type="button" onClick={() => setQuickAddOpen(true)}>
          <Plus size={16} /> <span>新建事项</span> <kbd>⌘K</kbd>
        </button>
        <nav>
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group}>
              <span className="nav-group-label">{group}</span>
              {visibleNavItems
                .filter((item) => item.group === group)
                .map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.page}
                      className={page === item.page ? 'active' : ''}
                      onClick={() => onNavigate(item.page)}
                      title={item.label}
                    >
                      <Icon size={18} />
                      <span>{item.label}</span>
                      {item.page === 'inbox' && inboxCount > 0 && <span className="nav-badge">{inboxCount}</span>}
                    </button>
                  );
                })}
            </div>
          ))}
        </nav>
        {(savedViews.data ?? []).length > 0 && (
          <div className="sidebar-pinned">
            <span className="nav-group-label">智能视图</span>
            {(savedViews.data ?? []).map((view) => (
              <div className="sidebar-view-row" key={view.id}>
                <button
                  type="button"
                  title={`套用到「${view.spec.page === 'work' ? '工作' : '个人'}」页`}
                  onClick={() => {
                    stashViewHandoff(view.spec);
                    onNavigate(view.spec.page);
                  }}
                >
                  <span>{view.name}</span>
                </button>
                <button className="ghost sm danger-text" type="button" title="删除视图" onClick={() => deleteView.mutate(view.id)}>
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        {pinnedTags.length > 0 && (
          <div className="sidebar-pinned">
            <span className="nav-group-label">固定标签</span>
            {pinnedTags.map((tag) => (
              <button
                key={tag.id}
                type="button"
                title={`查看标签「${tag.name}」`}
                onClick={() => {
                  sessionStorage.setItem('pa-open-tag', tag.id);
                  onNavigate('tags');
                }}
              >
                <span className="dot" style={{ background: tag.color }} />
                <span>{tag.name}</span>
              </button>
            ))}
          </div>
        )}
        <button className="sidebar-search" type="button" onClick={() => setSearchOpen(true)}>
          <Search size={16} /> <span>搜索</span> <kbd>⌘P</kbd>
        </button>
        <ReminderInbox session={session} onNavigate={onNavigate} desktopNotifications={desktopNotifications} />
        <div className="session-card">
          <span>{session.username}</span>
          <button className="icon-button" type="button" title="登出" onClick={() => logout.mutate()} disabled={logout.isPending}>
            <LogOut size={15} />
          </button>
        </div>
      </aside>
      <main className="content">
        {hasReminderIssue && (
          <button className="health-strip" type="button" onClick={() => setDiagOpen(true)}>
            <CircleAlert size={16} /> 投递异常：{health.data?.retry_count ?? 0} 条重试中，{health.data?.dead_count ?? 0} 条需人工处理（点击查看诊断）
          </button>
        )}
        {children}
      </main>
      <FocusBar session={session} />
      {quickAddOpen && <QuickAddDialog session={session} defaultScope={quickAddScope} onClose={() => setQuickAddOpen(false)} />}
      {searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} onOpenItem={openSearchItem} />}
      {shortcutHelpOpen && <ShortcutHelpDialog onClose={() => setShortcutHelpOpen(false)} />}
      {diagOpen && <ReminderDiagnosticsDialog session={session} onClose={() => setDiagOpen(false)} />}
    </div>
  );
}

function ReminderInbox({
  session,
  onNavigate,
  desktopNotifications,
}: {
  session: Session;
  onNavigate: (page: Page) => void;
  desktopNotifications: boolean;
}) {
  const queryClient = useQueryClient();
  // 服务端 ack/snooze：只拉「已投递且未确认且未稍后」的投递；30s 轮询同时承担 snooze 到期唤醒
  const deliveries = useQuery({
    queryKey: ['reminder-deliveries', 'unseen'],
    queryFn: api.unseenReminderDeliveries,
    refetchInterval: 30000,
  });
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });
  const [panelOpen, setPanelOpen] = useState(false);
  const [toasts, setToasts] = useState<ReminderDelivery[]>([]);
  const toastedRef = useRef<Set<string>>(new Set());

  const itemById = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of [...(workItems.data ?? []), ...(personalItems.data ?? [])]) map.set(item.id, item);
    return map;
  }, [workItems.data, personalItems.data]);

  const unacked = useMemo(
    () => [...(deliveries.data ?? [])].sort((a, b) => a.scheduled_for.localeCompare(b.scheduled_for)),
    [deliveries.data],
  );

  const ackMutation = useMutation({
    mutationFn: (deliveryId: string) => api.ackDelivery(session.csrf_token, deliveryId),
    onMutate: (deliveryId) => {
      queryClient.setQueryData<ReminderDelivery[]>(['reminder-deliveries', 'unseen'], (prev) =>
        (prev ?? []).filter((delivery) => delivery.id !== deliveryId),
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['reminder-deliveries'] }),
  });

  const snoozeMutation = useMutation({
    mutationFn: ({ deliveryId, until }: { deliveryId: string; until: string }) =>
      api.snoozeDelivery(session.csrf_token, deliveryId, until),
    onMutate: ({ deliveryId }) => {
      queryClient.setQueryData<ReminderDelivery[]>(['reminder-deliveries', 'unseen'], (prev) =>
        (prev ?? []).filter((delivery) => delivery.id !== deliveryId),
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['reminder-deliveries'] }),
  });

  useEffect(() => {
    const fresh = unacked.filter((delivery) => !toastedRef.current.has(delivery.id));
    if (fresh.length === 0) return;
    fresh.forEach((delivery) => toastedRef.current.add(delivery.id));
    const shown = fresh.slice(0, 3);
    setToasts((prev) => [...prev, ...shown]);
    if (desktopNotifications && 'Notification' in window && Notification.permission === 'granted') {
      shown.forEach((delivery) => {
        const item = itemById.get(delivery.item_id);
        const note = item?.notes?.trim();
        const notification = new Notification(item?.title ?? '事项提醒', {
          body: [`${formatScheduleTime(delivery.scheduled_for)} 到点`, note ? note.slice(0, 60) : null].filter(Boolean).join(' · '),
          tag: delivery.id,
          icon: '/icon.svg',
        });
        notification.onclick = () => {
          window.focus();
          notification.close();
          ack(delivery.id);
          if (item) navigateToItem(item);
        };
      });
    }
  }, [unacked, desktopNotifications, itemById]);

  function snoozeDelivery(delivery: ReminderDelivery, kind: '10m' | '1h' | 'tomorrow9') {
    toastedRef.current.delete(delivery.id);
    setToasts((prev) => prev.filter((toast) => toast.id !== delivery.id));
    snoozeMutation.mutate({ deliveryId: delivery.id, until: snoozeWakeAt(kind) });
  }

  const completeItem = useMutation({
    mutationFn: (item: Item) => api.patchItem(session.csrf_token, item, { status: 'done' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items', 'work'] });
      queryClient.invalidateQueries({ queryKey: ['items', 'personal'] });
      queryClient.invalidateQueries({ queryKey: ['reminder-deliveries'] });
      queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
    },
  });

  function ack(deliveryId: string) {
    setToasts((prev) => prev.filter((toast) => toast.id !== deliveryId));
    ackMutation.mutate(deliveryId);
  }

  function navigateToItem(item: Item) {
    window.sessionStorage.setItem('pa-open-item', item.id);
    onNavigate(item.scope === 'work' ? 'work' : 'personal');
  }

  function openDelivery(delivery: ReminderDelivery) {
    const item = itemById.get(delivery.item_id);
    ack(delivery.id);
    setPanelOpen(false);
    if (item) navigateToItem(item);
  }

  function completeDelivery(delivery: ReminderDelivery) {
    const item = itemById.get(delivery.item_id);
    ack(delivery.id);
    if (item && item.status !== 'done') completeItem.mutate(item);
  }

  function deliveryTitle(delivery: ReminderDelivery) {
    return itemById.get(delivery.item_id)?.title ?? '事项提醒';
  }

  function deliveryDetail(delivery: ReminderDelivery) {
    const item = itemById.get(delivery.item_id);
    return [`${formatScheduleTime(delivery.scheduled_for)} 到点`, item?.notes?.trim()].filter(Boolean).join(' · ');
  }

  return (
    <div className="reminder-inbox">
      <button className="reminder-bell" type="button" onClick={() => setPanelOpen((open) => !open)} title="提醒">
        <Bell size={18} />
        {unacked.length > 0 && <span className="reminder-badge">{unacked.length > 99 ? '99+' : unacked.length}</span>}
      </button>
      {panelOpen && (
        <div className="reminder-panel">
          <header>
            <strong>到点提醒</strong>
            {unacked.length > 0 && (
              <button className="ghost sm" type="button" onClick={() => unacked.forEach((delivery) => ack(delivery.id))}>
                全部已读
              </button>
            )}
          </header>
          {unacked.length === 0 && <p className="empty">暂无未读提醒</p>}
          {unacked.slice(0, 10).map((delivery) => (
            <article className="reminder-panel-row" key={delivery.id}>
              <button className="reminder-panel-main" type="button" onClick={() => openDelivery(delivery)}>
                <strong>{deliveryTitle(delivery)}</strong>
                <small>{deliveryDetail(delivery)}</small>
              </button>
              <div className="reminder-inline-actions">
                <button className="ghost sm" type="button" onClick={() => snoozeDelivery(delivery, '10m')}>
                  {snoozeLabel('10m')}
                </button>
                <button className="ghost sm" type="button" onClick={() => ack(delivery.id)}>
                  确认
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {toasts.length > 0 && (
        <div className="reminder-toasts">
          {toasts.map((delivery) => (
            <div className="reminder-toast" key={delivery.id}>
              <div className="reminder-toast-main">
                <Bell size={14} />
                <div>
                  <strong>{deliveryTitle(delivery)}</strong>
                  <small>{deliveryDetail(delivery)}</small>
                </div>
              </div>
              <div className="reminder-toast-actions">
                <button className="ghost sm" type="button" onClick={() => completeDelivery(delivery)}>
                  完成
                </button>
                <button className="ghost sm" type="button" onClick={() => openDelivery(delivery)}>
                  打开
                </button>
                <button className="ghost sm" type="button" onClick={() => snoozeDelivery(delivery, '10m')}>
                  {snoozeLabel('10m')}
                </button>
                <button className="ghost sm" type="button" onClick={() => snoozeDelivery(delivery, '1h')}>
                  {snoozeLabel('1h')}
                </button>
                <button className="ghost sm" type="button" onClick={() => snoozeDelivery(delivery, 'tomorrow9')}>
                  {snoozeLabel('tomorrow9')}
                </button>
                <button className="ghost sm" type="button" onClick={() => ack(delivery.id)}>
                  确认
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
