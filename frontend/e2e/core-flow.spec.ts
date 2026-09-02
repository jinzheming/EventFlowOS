import { expect, test } from '@playwright/test';

const session = {
  user_id: '00000000-0000-4000-8000-000000000001',
  username: 'local',
  csrf_token: 'csrf-token',
  timezone: 'Asia/Shanghai',
};

const emptyPreferences = {
  timezone: 'Asia/Shanghai',
  work_filters: {},
  personal_filters: {},
  calendar_filters: {},
  weekly_review_enabled: false,
  desktop_notifications: false,
  identity_scope_rules: [],
  digest_morning_enabled: false,
  digest_evening_enabled: false,
  digest_morning_time: '08:30',
  digest_evening_time: '18:00',
  ics_token: null,
};

const createdItem = {
  id: '10000000-0000-4000-8000-000000000001',
  scope: 'personal',
  project_id: null,
  project_name: null,
  title: '约牙医',
  notes: null,
  status: 'planned',
  priority: 'normal',
  all_day: false,
  start_at: '2026-09-03T07:00:00Z',
  due_at: '2026-09-03T08:00:00Z',
  start_date: null,
  due_date: null,
  waiting_on: null,
  waiting_follow_up_date: null,
  recurrence_freq: null,
  recurrence_interval: null,
  recurrence_until: null,
  recurrence_count: null,
  estimated_minutes: 60,
  completed_at: null,
  cancelled_at: null,
  archived_at: null,
  deleted_at: null,
  created_by_actor: 'human',
  updated_by_actor: 'human',
  source_context: {},
  execution_output: {},
  version: 1,
  created_at: '2026-09-02T00:00:00Z',
  updated_at: '2026-09-02T00:00:00Z',
  tags: [],
  people: [],
};

test('creates a quick-add item with a reminder from the authenticated shell', async ({ page }) => {
  let itemCreated = false;
  let reminderCreated = false;

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === '/api/v1/auth/session') {
      await route.fulfill({ json: session });
      return;
    }
    if (path === '/api/v1/preferences') {
      await route.fulfill({ json: emptyPreferences });
      return;
    }
    if (path === '/api/v1/reminders/health') {
      await route.fulfill({ json: { worker_seen_recently: true, pending_count: 0, retry_count: 0, dead_count: 0, max_lag_seconds: null } });
      return;
    }
    if (path === '/api/v1/items' && method === 'GET') {
      await route.fulfill({ json: itemCreated ? [createdItem] : [] });
      return;
    }
    if (path === '/api/v1/items' && method === 'POST') {
      itemCreated = true;
      expect(request.headers()['x-csrf-token']).toBe('csrf-token');
      await route.fulfill({ status: 201, json: createdItem });
      return;
    }
    if (path === `/api/v1/items/${createdItem.id}/reminder` && method === 'PUT') {
      reminderCreated = true;
      expect(request.headers()['x-csrf-token']).toBe('csrf-token');
      await route.fulfill({ json: { id: '20000000-0000-4000-8000-000000000001', item_id: createdItem.id, timing: 'before_start', offset_minutes: 60, timezone: 'Asia/Shanghai', external_enabled: false, active: true, created_at: '2026-09-02T00:00:00Z', updated_at: '2026-09-02T00:00:00Z' } });
      return;
    }
    if (path === '/api/v1/projects' || path === '/api/v1/tags' || path === '/api/v1/people' || path === '/api/v1/saved-views' || path === '/api/v1/agent-proposals') {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === '/api/v1/focus/active') {
      await route.fulfill({ json: null });
      return;
    }
    if (path === '/api/v1/focus/today') {
      await route.fulfill({ json: { total_seconds: 0, session_count: 0 } });
      return;
    }
    if (path === '/api/v1/habits/week' || path === '/api/v1/reminders/deliveries') {
      await route.fulfill({ json: [] });
      return;
    }

    await route.fulfill({ json: {} });
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: '今日' })).toBeVisible();

  await page.getByRole('button', { name: /新建事项/ }).click();
  await page.getByPlaceholder(/例如/).fill('明天下午3点 约牙医 预计1小时 提前1小时提醒 #个人');
  await expect(page.getByText('约牙医')).toBeVisible();
  await page.getByRole('button', { name: /创建事项/ }).click();

  await expect.poll(() => itemCreated).toBe(true);
  await expect.poll(() => reminderCreated).toBe(true);
});
