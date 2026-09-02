import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setAppTimezone } from './dates';
import { parseQuickAdd, resolveScope } from './quickAdd';

describe('parseQuickAdd', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-02T00:00:00Z'));
    setAppTimezone('Asia/Shanghai');
  });

  afterEach(() => {
    setAppTimezone(null);
    vi.useRealTimers();
  });

  it('extracts personal scope, time, duration, and reminder intent', () => {
    expect(parseQuickAdd('明天下午3点 约牙医 预计1小时 提前30分钟提醒 #个人')).toMatchObject({
      title: '约牙医',
      scope: 'personal',
      start_date: '2026-09-03',
      start_time: '15:00',
      estimated_minutes: 60,
      reminder_offset: 30,
      recurrence: '',
      status: null,
    });
  });

  it('anchors weekly recurrence to the next matching weekday', () => {
    expect(parseQuickAdd('每周一 10点 项目例会 #工作')).toMatchObject({
      title: '项目例会',
      scope: 'work',
      start_date: '2026-09-07',
      start_time: '10:00',
      recurrence: 'weekly',
      estimated_minutes: 60,
    });
  });

  it('detects waiting people from prefix syntax', () => {
    expect(parseQuickAdd('!张三 等材料 下周五')).toMatchObject({
      title: '等材料',
      waiting_on: '张三',
      person_role: 'waiting',
      status: 'waiting',
      start_date: '2026-09-11',
    });
  });
});

describe('resolveScope', () => {
  it('lets explicit scope win over identity rules', () => {
    const parsed = parseQuickAdd('@李四 准备采购 #个人');
    expect(
      resolveScope(parsed, [{ keyword: 'vendor', scope: 'work' }], [{ name: '李四', identity: 'Vendor' }]),
    ).toEqual({ scope: 'personal', source: 'explicit' });
  });

  it('routes collaborator identity matches when no explicit scope exists', () => {
    const parsed = parseQuickAdd('@李四 准备采购');
    expect(
      resolveScope(parsed, [{ keyword: 'vendor', scope: 'work' }], [{ name: '李四', identity: 'Vendor partner' }]),
    ).toEqual({ scope: 'work', source: 'identity' });
  });

  it('falls back to inbox when no scope signal is present', () => {
    expect(resolveScope(parseQuickAdd('整理资料'), [], [])).toEqual({ scope: null, source: 'inbox' });
  });
});
