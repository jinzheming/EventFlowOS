export type Scope = 'work' | 'personal';
export type ItemStatus = 'inbox' | 'planned' | 'in_progress' | 'waiting' | 'done' | 'cancelled';
export type Priority = 'low' | 'normal' | 'high' | 'urgent';
export type ProjectStatus = 'planned' | 'active' | 'on_hold' | 'completed' | 'cancelled';
export type ProjectHealth = 'unknown' | 'on_track' | 'at_risk' | 'blocked';
export type ActorType = 'human' | 'agent' | 'system';
export type AgentProposalSourceType = 'agent' | 'feishu_im' | 'tencent_meeting';
export type AgentProposalRiskTier = 'l1' | 'l2' | 'l3';
export type AgentProposalState = 'pending' | 'approved' | 'edited_approved' | 'rejected' | 'ignored' | 'expired';
export type AgentProposalAction = 'create_item' | 'patch_item';
export type IntakeOrigin = 'web' | 'agent' | 'api';
export type IntakeNormalization = 'none' | 'llm';

export interface Session {
  user_id: string;
  username: string;
  csrf_token: string;
  timezone: string;
}

export interface PatToken {
  id: string;
  name: string;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface PatCreated extends PatToken {
  token: string;
}

export type WebhookEventType =
  | 'item.created'
  | 'item.completed'
  | 'reminder.fired'
  | 'reminder.acked'
  | 'reminder.snoozed'
  | 'delivery.failed';

export interface WebhookSubscription {
  id: string;
  name: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WebhookCreatedSub extends WebhookSubscription {
  secret: string;
}

export interface WebhookEvent {
  id: string;
  event_type: string;
  aggregate: string;
  aggregate_id: string;
  payload: Record<string, unknown>;
  created_at: string;
  attempt_count: number;
  status: string;
  last_error_code: string | null;
  last_error_message: string | null;
}

export type PersonRole = 'together' | 'waiting';

export interface ItemPerson {
  id: string;
  name: string;
  identity: string | null;
  active: boolean;
  role: PersonRole;
}

export interface Person {
  id: string;
  name: string;
  identity: string | null;
  note: string | null;
  active: boolean;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface ItemTag {
  id: string;
  name: string;
  color: string;
  parent_id: string | null;
}

export interface Tag {
  id: string;
  name: string;
  color: string;
  parent_id: string | null;
  pinned: boolean;
  item_count: number;
  children: Tag[];
}

export interface Item {
  id: string;
  scope: Scope;
  project_id: string | null;
  project_name: string | null;
  title: string;
  notes: string | null;
  status: ItemStatus;
  priority: Priority;
  all_day: boolean;
  start_at: string | null;
  due_at: string | null;
  start_date: string | null;
  due_date: string | null;
  waiting_on: string | null;
  waiting_follow_up_date: string | null;
  recurrence_freq: 'daily' | 'weekly' | 'monthly' | null;
  recurrence_interval: number | null;
  recurrence_until: string | null;
  recurrence_count: number | null;
  estimated_minutes: number | null;
  completed_at: string | null;
  cancelled_at: string | null;
  archived_at: string | null;
  deleted_at: string | null;
  created_by_actor: ActorType | string;
  updated_by_actor: ActorType | string;
  source_context: Record<string, unknown>;
  execution_output: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
  tags: ItemTag[];
  people: ItemPerson[];
}

export type ItemPayload = Omit<Partial<Item>, 'people'> & {
  tag_ids?: string[] | null;
  people?: Array<{ person_id: string; role: PersonRole } | ItemPerson> | null;
  intake_text?: string | null;
  intake_scope_source?: string | null;
  intake_origin?: IntakeOrigin | null;
  intake_normalization?: IntakeNormalization | null;
};

export interface AgentProposal {
  id: string;
  source_type: AgentProposalSourceType;
  source_ref: string | null;
  risk_tier: AgentProposalRiskTier;
  confidence: number | null;
  state: AgentProposalState;
  proposed_action: AgentProposalAction;
  proposed_payload: Record<string, unknown>;
  evidence: Record<string, unknown>;
  reason: string | null;
  target_item_id: string | null;
  applied_item_id: string | null;
  expires_at: string | null;
  decided_at: string | null;
  decided_by_actor: ActorType | string | null;
  decision_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentProposalDecision {
  proposal: AgentProposal;
  item: Item | null;
}

export type TagPayload = Partial<Pick<Tag, 'name' | 'color' | 'parent_id' | 'pinned'>>;

export interface FocusSession {
  id: string;
  item_id: string;
  item_title: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
}

export interface FocusSummary {
  total_seconds: number;
  session_count: number;
}

export interface HabitWeek {
  item_id: string;
  title: string;
  scope: string;
  recurrence_freq: string;
  week: boolean[];
  week_done: number;
  week_target: number;
  streak: number;
  today_done: boolean;
}

export interface FocusCalibration {
  session_count: number;
  actual_seconds: number;
  calibrated_count: number;
  estimated_seconds: number;
  calibrated_actual_seconds: number;
}

export interface SavedViewSpec {
  page: 'work' | 'personal';
  quickFilter: string;
  highPriority: boolean;
  search: string;
}

export interface SavedView {
  id: string;
  name: string;
  spec: SavedViewSpec;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface ReminderPut {
  timing: 'at_start' | 'before_start' | 'before_due';
  offset_minutes: number;
  timezone: string;
  external_enabled: boolean;
}

export interface Project {
  id: string;
  name: string;
  goal: string | null;
  status: ProjectStatus;
  health: ProjectHealth;
  progress_mode: 'manual' | 'milestone';
  progress_percent: number | null;
  risk_summary: string | null;
  next_step: string | null;
  next_review_at: string | null;
  due_date: string | null;
  color: string;
  group_id: string | null;
  group_name: string | null;
  archived_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectGroup {
  id: string;
  name: string;
  color: string;
  sort_order: number;
  archived_at: string | null;
  project_count: number;
  risk_count: number;
  created_at: string;
  updated_at: string;
}

export interface Milestone {
  id: string;
  project_id: string;
  title: string;
  status: 'pending' | 'done' | 'cancelled';
  due_date: string | null;
  weight: number;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface CalendarEvent {
  id: string;
  kind: 'work_item' | 'personal_item' | 'milestone';
  title: string;
  start: string;
  end: string | null;
  all_day: boolean;
  source_id: string;
  project_id: string | null;
  status: string;
  color: string;
}

export interface Reminder {
  id: string;
  item_id: string;
  timing: 'at_start' | 'before_start' | 'before_due';
  offset_minutes: number;
  timezone: string;
  external_enabled: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReminderDelivery {
  id: string;
  reminder_id: string;
  item_id: string;  channel: 'in_app' | 'feishu' | 'ntfy';
  scheduled_for: string;
  status: 'pending' | 'delivering' | 'delivered' | 'retry_wait' | 'dead' | 'cancelled';
  attempt_count: number;
  last_error_code: string | null;
  last_error_message: string | null;
  delivered_at: string | null;
  acknowledged_at: string | null;
  snooze_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReminderHealth {
  worker_seen_recently: boolean;
  pending_count: number;
  retry_count: number;
  dead_count: number;
  max_lag_seconds: number | null;
}

export interface IdentityScopeRule {
  keyword: string;
  scope: 'work' | 'personal';
}

export interface Preferences {
  timezone: string;
  work_filters: Record<string, unknown>;
  personal_filters: Record<string, unknown>;
  calendar_filters: Record<string, unknown>;
  weekly_review_enabled: boolean;
  desktop_notifications: boolean;
  identity_scope_rules: IdentityScopeRule[];
  digest_morning_enabled: boolean;
  digest_evening_enabled: boolean;
  digest_morning_time: string;
  digest_evening_time: string;
  ics_token: string | null;
}

async function request<T>(path: string, init: RequestInit = {}, csrf?: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(csrf ? { 'x-csrf-token': csrf } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(problem.detail || response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  session: () => request<Session>('/auth/session'),
  login: (username: string, password: string) =>
    request<Session>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  patTokens: () => request<PatToken[]>('/auth/tokens'),
  createPatToken: (csrf: string, payload: { name: string; scopes?: string[]; expires_in_days?: number }) =>
    request<PatCreated>('/auth/tokens', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  revokePatToken: (csrf: string, tokenId: string) =>
    request<void>(`/auth/tokens/${tokenId}`, { method: 'DELETE' }, csrf),
  webhooks: () => request<WebhookSubscription[]>('/webhooks'),
  createWebhook: (csrf: string, payload: { name: string; url: string; events: string[] }) =>
    request<WebhookCreatedSub>('/webhooks', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  deleteWebhook: (csrf: string, webhookId: string) =>
    request<void>(`/webhooks/${webhookId}`, { method: 'DELETE' }, csrf),
  webhookEvents: (limit = 20) => request<WebhookEvent[]>(`/webhooks/events?limit=${limit}`),
  items: (scope: Scope, includeArchived = false, search = '') =>
    request<Item[]>(
      `/items?scope=${scope}&include_archived=${includeArchived}${search ? `&search=${encodeURIComponent(search)}` : ''}`,
    ),
  agentProposals: (state: AgentProposalState = 'pending') =>
    request<AgentProposal[]>(`/agent-proposals?state=${state}&limit=500`),
  approveProposal: (csrf: string, proposalId: string, payload: { edited_payload?: Record<string, unknown>; decision_note?: string | null } = {}) =>
    request<AgentProposalDecision>(`/agent-proposals/${proposalId}/approve`, { method: 'POST', body: JSON.stringify(payload) }, csrf),
  rejectProposal: (csrf: string, proposalId: string, decision_note?: string | null) =>
    request<AgentProposal>(`/agent-proposals/${proposalId}/reject`, { method: 'POST', body: JSON.stringify({ decision_note }) }, csrf),
  ignoreProposal: (csrf: string, proposalId: string, decision_note?: string | null) =>
    request<AgentProposal>(`/agent-proposals/${proposalId}/ignore`, { method: 'POST', body: JSON.stringify({ decision_note }) }, csrf),
  createItem: (csrf: string, payload: ItemPayload & { title: string; scope: Scope }) =>
    request<Item>('/items', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  patchItem: (csrf: string, item: Item, payload: ItemPayload) =>
    request<Item>(
      `/items/${item.id}`,
      { method: 'PATCH', body: JSON.stringify(payload), headers: { 'if-match': `v${item.version}` } },
      csrf,
    ),
  putReminder: (csrf: string, itemId: string, payload: ReminderPut) =>
    request(`/items/${itemId}/reminder`, { method: 'PUT', body: JSON.stringify(payload) }, csrf),
  getReminder: async (itemId: string): Promise<Reminder | null> => {
    const response = await fetch(`/api/v1/items/${itemId}/reminder`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(response.statusText);
    return response.json() as Promise<Reminder>;
  },
  reminderDeliveries: (channel?: string, status?: string) =>
    request<ReminderDelivery[]>(
      `/reminders/deliveries?limit=200${channel ? `&channel=${channel}` : ''}${status ? `&status=${status}` : ''}`,
    ),
  retryDelivery: (csrf: string, deliveryId: string) =>
    request<ReminderDelivery>(`/reminders/deliveries/${deliveryId}/retry`, { method: 'POST' }, csrf),
  unseenReminderDeliveries: () =>
    request<ReminderDelivery[]>('/reminders/deliveries?limit=200&channel=in_app&status=delivered&unseen=true'),
  ackDelivery: (csrf: string, deliveryId: string) =>
    request<ReminderDelivery>(`/reminders/deliveries/${deliveryId}/ack`, { method: 'POST' }, csrf),
  snoozeDelivery: (csrf: string, deliveryId: string, snoozeUntil: string) =>
    request<ReminderDelivery>(`/reminders/deliveries/${deliveryId}/snooze`, { method: 'POST', body: JSON.stringify({ snooze_until: snoozeUntil }) }, csrf),
  trashedItems: () => request<Item[]>('/items?deleted=true&limit=500'),
  deleteItem: (csrf: string, itemId: string) => request<void>(`/items/${itemId}`, { method: 'DELETE' }, csrf),
  restoreDeletedItem: (csrf: string, itemId: string) =>
    request<Item>(`/items/${itemId}/restore-deleted`, { method: 'POST' }, csrf),
  purgeItem: (csrf: string, itemId: string) => request<void>(`/items/${itemId}/purge`, { method: 'DELETE' }, csrf),
  reminderChannels: () => request<{ feishu_configured: boolean; ntfy_configured: boolean }>('/reminders/channels'),
  pushVapidKey: () => request<{ enabled: boolean; public_key: string | null }>('/push/vapid-key'),
  subscribePush: (csrf: string, subscription: { endpoint: string; p256dh: string; auth: string }) =>
    request('/push/subscriptions', { method: 'POST', body: JSON.stringify(subscription) }, csrf),
  unsubscribePush: (csrf: string, endpoint: string) =>
    request<void>('/push/subscriptions', { method: 'DELETE', body: JSON.stringify({ endpoint }) }, csrf),
  milestones: (projectId: string) => request<Milestone[]>(`/projects/${projectId}/milestones`),
  createMilestone: (csrf: string, projectId: string, payload: { title: string; due_date: string | null }) =>
    request<Milestone>(`/projects/${projectId}/milestones`, { method: 'POST', body: JSON.stringify(payload) }, csrf),
  patchMilestone: (csrf: string, projectId: string, milestoneId: string, payload: Partial<Pick<Milestone, 'title' | 'status' | 'due_date'>>) =>
    request<Milestone>(`/projects/${projectId}/milestones/${milestoneId}`, { method: 'PATCH', body: JSON.stringify(payload) }, csrf),
  deleteMilestone: (csrf: string, projectId: string, milestoneId: string) =>
    request<void>(`/projects/${projectId}/milestones/${milestoneId}`, { method: 'DELETE' }, csrf),
  deleteReminder: (csrf: string, itemId: string) => request(`/items/${itemId}/reminder`, { method: 'DELETE' }, csrf),
  archiveItem: (csrf: string, itemId: string) => request<Item>(`/items/${itemId}/archive`, { method: 'POST' }, csrf),
  restoreItem: (csrf: string, itemId: string) => request<Item>(`/items/${itemId}/restore`, { method: 'POST' }, csrf),
  projects: () => request<Project[]>('/projects'),
  createProject: (csrf: string, payload: Partial<Project> & { name: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  patchProject: (csrf: string, project: Project, payload: Partial<Project>) =>
    request<Project>(
      `/projects/${project.id}`,
      { method: 'PATCH', body: JSON.stringify(payload), headers: { 'if-match': `v${project.version}` } },
      csrf,
    ),
  projectItems: (projectId: string) => request<Item[]>(`/projects/${projectId}/items`),
  projectGroups: (includeArchived = false) => request<ProjectGroup[]>(`/project-groups${includeArchived ? '?include_archived=true' : ''}`),
  createProjectGroup: (csrf: string, payload: { name: string; color?: string; sort_order?: number }) =>
    request<ProjectGroup>('/project-groups', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  patchProjectGroup: (csrf: string, groupId: string, payload: Partial<Pick<ProjectGroup, 'name' | 'color' | 'sort_order'>>) =>
    request<ProjectGroup>(`/project-groups/${groupId}`, { method: 'PATCH', body: JSON.stringify(payload) }, csrf),
  archiveProjectGroup: (csrf: string, groupId: string) => request<ProjectGroup>(`/project-groups/${groupId}/archive`, { method: 'POST' }, csrf),
  restoreProjectGroup: (csrf: string, groupId: string) => request<ProjectGroup>(`/project-groups/${groupId}/restore`, { method: 'POST' }, csrf),
  calendarEvents: (from: string, to: string, kinds?: string) =>
    request<CalendarEvent[]>(`/calendar/events?from=${from}&to=${to}${kinds ? `&kinds=${kinds}` : ''}`),
  reminderHealth: () => request<ReminderHealth>('/reminders/health'),
  startFocus: (csrf: string, itemId: string) => request<FocusSession>(`/items/${itemId}/focus/start`, { method: 'POST' }, csrf),
  stopFocus: (csrf: string, itemId: string) => request<FocusSession>(`/items/${itemId}/focus/stop`, { method: 'POST' }, csrf),
  activeFocus: () => request<FocusSession | null>('/focus/active'),
  focusToday: () => request<FocusSummary>('/focus/today'),
  focusSummary: (itemId: string) => request<FocusSummary>(`/items/${itemId}/focus/summary`),
  habitsWeek: (weekOffset = 0) => request<HabitWeek[]>(`/habits/week${weekOffset ? `?week_offset=${weekOffset}` : ''}`),
  focusWeek: () => request<FocusCalibration>('/focus/week'),
  checkin: (csrf: string, itemId: string) => request<void>(`/items/${itemId}/checkin`, { method: 'POST', body: JSON.stringify({}) }, csrf),
  undoCheckin: (csrf: string, itemId: string, date: string) => request<void>(`/items/${itemId}/checkin/${date}`, { method: 'DELETE' }, csrf),
  savedViews: () => request<SavedView[]>('/saved-views'),
  regenerateFeedToken: (csrf: string) => request<{ ics_token: string }>('/calendar/feed-token', { method: 'POST' }, csrf),
  createSavedView: (csrf: string, payload: { name: string; spec: SavedViewSpec; sort_order?: number }) =>
    request<SavedView>('/saved-views', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  patchSavedView: (csrf: string, viewId: string, payload: Partial<Pick<SavedView, 'name' | 'sort_order'> & { spec: SavedViewSpec }>) =>
    request<SavedView>(`/saved-views/${viewId}`, { method: 'PATCH', body: JSON.stringify(payload) }, csrf),
  deleteSavedView: (csrf: string, viewId: string) => request<void>(`/saved-views/${viewId}`, { method: 'DELETE' }, csrf),
  preferences: () => request<Preferences>('/preferences'),
  patchPreferences: (csrf: string, payload: Partial<Preferences>) =>
    request<Preferences>('/preferences', { method: 'PATCH', body: JSON.stringify(payload) }, csrf),
  people: (includeInactive = true) => request<Person[]>(`/people?include_inactive=${includeInactive}`),
  createPerson: (csrf: string, payload: { name: string; identity?: string | null; note?: string | null }) =>
    request<Person>('/people', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  patchPerson: (csrf: string, personId: string, payload: Partial<Pick<Person, 'name' | 'identity' | 'note' | 'active'>>) =>
    request<Person>(`/people/${personId}`, { method: 'PATCH', body: JSON.stringify(payload) }, csrf),
  deletePerson: (csrf: string, personId: string) => request<void>(`/people/${personId}`, { method: 'DELETE' }, csrf),
  tags: () => request<Tag[]>('/tags'),
  createTag: (csrf: string, payload: { name: string; color?: string; parent_id?: string | null }) =>
    request<Tag>('/tags', { method: 'POST', body: JSON.stringify(payload) }, csrf),
  patchTag: (csrf: string, tagId: string, payload: TagPayload) =>
    request<Tag>(`/tags/${tagId}`, { method: 'PATCH', body: JSON.stringify(payload) }, csrf),
  deleteTag: (csrf: string, tagId: string) => request<void>(`/tags/${tagId}`, { method: 'DELETE' }, csrf),
  tagItems: (tagId: string, options: { include_done?: boolean; scope?: Scope; recursive?: boolean }) => {
    const query = new URLSearchParams();
    if (options.include_done !== undefined) query.set('include_done', String(options.include_done));
    if (options.scope) query.set('scope', options.scope);
    if (options.recursive !== undefined) query.set('recursive', String(options.recursive));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return request<Item[]>(`/tags/${tagId}/items${suffix}`);
  },
  logout: (csrf: string) => request<void>('/auth/logout', { method: 'POST' }, csrf),
};
