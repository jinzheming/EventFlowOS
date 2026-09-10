import { test } from 'node:test';
import assert from 'node:assert/strict';
import { groupHistoryItems, historyWindowForItems } from './src/lib/items.ts';

function item(overrides) {
  return {
    id: overrides.id ?? 'item-1',
    scope: 'work',
    project_id: null,
    project_name: null,
    title: overrides.title ?? '测试事项',
    notes: null,
    status: 'done',
    priority: 'normal',
    all_day: true,
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
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    tags: [],
    people: [],
    ...overrides,
  };
}

function doneItem(index, completedAt) {
  return item({
    id: `done-${index}`,
    title: `done-${index}`,
    completed_at: completedAt,
    updated_at: completedAt,
  });
}

test('history groups items by completion week and sorts within the week by completion time', () => {
  const groups = groupHistoryItems(
    [
      doneItem(1, '2000-01-04T10:00:00Z'),
      doneItem(2, '2000-01-04T12:00:00Z'),
      doneItem(3, '1999-12-28T09:00:00Z'),
    ],
    'done',
  );

  assert.equal(groups[0].label, '2000-01-03 - 2000-01-09');
  assert.deepEqual(groups[0].items.map((entry) => entry.id), ['done-2', 'done-1']);
  assert.equal(groups[1].label, '1999-12-27 - 2000-01-02');
});

test('history window includes the whole boundary week after the first 30 items', () => {
  const latestWeek = Array.from({ length: 29 }, (_, index) =>
    doneItem(index, `2026-08-31T${String(23 - (index % 24)).padStart(2, '0')}:00:00Z`),
  );
  const boundaryWeek = Array.from({ length: 5 }, (_, index) =>
    doneItem(index + 29, `2026-08-24T${String(23 - index).padStart(2, '0')}:00:00Z`),
  );
  const olderWeek = [doneItem(99, '2026-08-17T12:00:00Z')];
  const window = historyWindowForItems([...olderWeek, ...boundaryWeek, ...latestWeek], 'done', 30);

  assert.equal(window.visibleCount, 34);
  assert.equal(window.items.length, 34);
  assert.equal(window.hasMore, true);
});

test('archived history uses archived_at when an item was not completed', () => {
  const groups = groupHistoryItems(
    [
      item({ id: 'archived-only', title: 'archived-only', status: 'planned', archived_at: '2000-02-03T09:00:00Z' }),
      item({ id: 'done-archived', title: 'done-archived', completed_at: '2000-01-04T12:00:00Z', archived_at: '2000-02-10T09:00:00Z' }),
    ],
    'archived',
  );

  assert.equal(groups[0].label, '2000-01-31 - 2000-02-06');
  assert.deepEqual(groups[0].items.map((entry) => entry.id), ['archived-only']);
  assert.equal(groups[1].label, '2000-01-03 - 2000-01-09');
  assert.deepEqual(groups[1].items.map((entry) => entry.id), ['done-archived']);
});
