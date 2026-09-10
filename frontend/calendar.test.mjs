import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hasAnySchedule, hasDateOnlySchedule, timedSchedulesForItem } from './src/lib/calendar.ts';

function item(overrides) {
  return {
    id: 'item-1',
    scope: 'work',
    project_id: null,
    project_name: null,
    title: '测试事项',
    notes: null,
    status: 'planned',
    priority: 'normal',
    all_day: false,
    start_at: null,
    due_at: null,
    start_date: null,
    due_date: null,
    waiting_on: null,
    waiting_follow_up_date: null,
    recurrence_freq: null,
    recurrence_interval: null,
    recurrence_until: null,
    recurrence_count: null,
    estimated_minutes: null,
    completed_at: null,
    cancelled_at: null,
    archived_at: null,
    deleted_at: null,
    created_by_actor: 'human',
    updated_by_actor: 'human',
    source_context: {},
    execution_output: {},
    version: 1,
    created_at: '2026-08-29T00:00:00Z',
    updated_at: '2026-08-29T00:00:00Z',
    tags: [],
    ...overrides,
  };
}

test('calendar schedules include completed items only when requested', () => {
  const doneTimed = item({
    status: 'done',
    start_at: '2026-08-29T09:00:00Z',
    due_at: '2026-08-29T10:00:00Z',
    completed_at: '2026-08-29T10:05:00Z',
  });

  assert.equal(timedSchedulesForItem(doneTimed).length, 0);
  assert.equal(timedSchedulesForItem(doneTimed, { includeDone: true }).length, 2);
  assert.equal(hasAnySchedule(doneTimed), false);
  assert.equal(hasAnySchedule(doneTimed, { includeDone: true }), true);
});

test('calendar date-only schedules include completed items only when requested', () => {
  const doneDateOnly = item({
    status: 'done',
    all_day: true,
    due_date: '2026-08-29',
    completed_at: '2026-08-29T10:05:00Z',
  });

  assert.equal(hasDateOnlySchedule(doneDateOnly), false);
  assert.equal(hasDateOnlySchedule(doneDateOnly, { includeDone: true }), true);
  assert.equal(hasAnySchedule(doneDateOnly), false);
  assert.equal(hasAnySchedule(doneDateOnly, { includeDone: true }), true);
});
