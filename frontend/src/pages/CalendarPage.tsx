import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { api, Item, Session } from '../api/client';
import { CalendarScheduleRow } from '../components/CalendarScheduleRow';
import { PersonalItemDrawer } from '../components/PersonalItemDrawer';
import { QuickFilterBar } from '../components/QuickFilterBar';
import { WeekGrid } from '../components/WeekGrid';
import { WorkItemDrawer } from '../components/WorkItemDrawer';
import { usePatchItem, useSaveItemWithReminder } from '../hooks/useItemActions';
import { useUndo } from '../hooks/useUndo';
import { calendarQuickFilters, ItemQuickFilter, matchesQuickFilter } from '../lib/itemFilters';
import {
  CalendarScopeFilter,
  buildDateOnlyTimePatch,
  compareDateOnlyItems,
  compareTimedSchedules,
  dateOnlyLabel,
  dateOnlyTimeOptions,
  groupTimedSchedules,
  hasDateOnlySchedule,
  timedSchedulesForItem,
} from '../lib/calendar';
import { addDaysString, localDateTimeParts, todayString } from '../lib/dates';
import { matchesItemSearch } from '../lib/items';
import { MonthGrid } from '../components/MonthGrid';
import { buildDragPatch, buildResizePatch, buildStartResizePatch, eventMatchesFilters, monthDates, shiftDateString, splitEventsForMonth, splitEventsForWeek, weekDates, weekOffsetForDate } from '../lib/week';

type CalendarView = 'week' | 'month' | 'list';

function initialView(): CalendarView {
  const stored = window.localStorage.getItem('pa-calendar-view');
  return stored === 'list' || stored === 'month' ? stored : 'week';
}

export function CalendarPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const [scopeFilter, setScopeFilter] = useState<CalendarScopeFilter>('all');
  const [search, setSearch] = useState('');
  const [quickFilter, setQuickFilter] = useState<ItemQuickFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<CalendarView>(initialView);
  const [showDone, setShowDone] = useState(() => localStorage.getItem('pa-calendar-show-done') !== '0');
  const [dragEnabled, setDragEnabled] = useState(() => localStorage.getItem('pa-calendar-drag-enabled') !== '0');
  const [filterOpen, setFilterOpen] = useState(false);
  const [displayOpen, setDisplayOpen] = useState(false);
  const [weekOffset, setWeekOffset] = useState(0);
  const [monthOffset, setMonthOffset] = useState(0);
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.projects });
  const workItems = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true) });
  const personalItems = useQuery({ queryKey: ['items', 'personal'], queryFn: () => api.items('personal', true) });
  const dates = useMemo(() => weekDates(weekOffset), [weekOffset]);
  const weekKinds = scopeFilter === 'all' ? undefined : scopeFilter === 'work' ? 'work_item,milestone' : 'personal_item';
  const weekEvents = useQuery({
    queryKey: ['calendar', 'week', dates[0], weekKinds ?? 'all'],
    queryFn: () => api.calendarEvents(dates[0], shiftDateString(dates[6], 1), weekKinds),
    enabled: view === 'week',
  });
  const filterEvents = (list: typeof weekEvents.data) =>
    (list ?? []).filter(
      (event) => (showDone || event.status !== 'done') && eventMatchesFilters(event, scopeFilter, quickFilter),
    );
  const weekBuckets = useMemo(() => splitEventsForWeek(filterEvents(weekEvents.data), dates), [weekEvents.data, dates, showDone, scopeFilter, quickFilter]);
  const mDates = useMemo(() => monthDates(monthOffset), [monthOffset]);
  const monthEvents = useQuery({
    queryKey: ['calendar', 'month', mDates[0], weekKinds ?? 'all'],
    queryFn: () => api.calendarEvents(mDates[0], shiftDateString(mDates[41], 1), weekKinds),
    enabled: view === 'month',
  });
  const monthBuckets = useMemo(() => splitEventsForMonth(filterEvents(monthEvents.data), mDates), [monthEvents.data, mDates, showDone, scopeFilter, quickFilter]);
  const allItems = useMemo(() => [...(workItems.data ?? []), ...(personalItems.data ?? [])], [personalItems.data, workItems.data]);
  const projectById = useMemo(() => new Map((projects.data ?? []).map((project) => [project.id, project])), [projects.data]);
  const items = useMemo(
    () =>
      allItems.filter(
        (item) =>
          (scopeFilter === 'all' || item.scope === scopeFilter) &&
          matchesItemSearch(item, search, projectById) &&
          matchesQuickFilter(item, quickFilter),
      ),
    [allItems, projectById, scopeFilter, search, quickFilter],
  );
  const selected = allItems.find((item) => item.id === selectedId) ?? null;
  const timedSchedules = useMemo(() => items.flatMap(timedSchedulesForItem).sort(compareTimedSchedules), [items]);
  const dateOnlyItems = useMemo(() => items.filter(hasDateOnlySchedule).sort(compareDateOnlyItems), [items]);
  const grouped = useMemo(() => groupTimedSchedules(timedSchedules), [timedSchedules]);
  const todayCount = timedSchedules.filter((schedule) => localDateTimeParts(schedule.time).date === todayString()).length;
  const weekCount = timedSchedules.filter((schedule) => {
    const date = localDateTimeParts(schedule.time).date;
    return date > todayString() && date <= addDaysString(7);
  }).length;
  const activeFilterCount = (scopeFilter !== 'all' ? 1 : 0) + (quickFilter !== 'all' ? 1 : 0);
  const loading = workItems.isLoading || personalItems.isLoading;
  const error = workItems.error?.message ?? personalItems.error?.message;

  function invalidateCalendarItems() {
    queryClient.invalidateQueries({ queryKey: ['items', 'work'] });
    queryClient.invalidateQueries({ queryKey: ['items', 'personal'] });
    queryClient.invalidateQueries({ queryKey: ['calendar'] });
    queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
  }

  const patchCalendarItem = usePatchItem(session, (item) => {
    setSelectedId(item.id);
    invalidateCalendarItems();
  });

  const saveCalendarItem = useSaveItemWithReminder(session, (item) => {
    setSelectedId(item.id);
    invalidateCalendarItems();
  });

  const undo = useUndo();

  // 软删除：进回收站（设置页），撤销即恢复
  function deleteFromDrawer(item: Item) {
    void api.deleteItem(session.csrf_token, item.id).then(() => {
      setSelectedId(null);
      invalidateCalendarItems();
      queryClient.invalidateQueries({ queryKey: ['items-trash'] });
      undo.pushUndo(`已删除「${item.title}」（回收站可恢复）`, () => {
        void api.restoreDeletedItem(session.csrf_token, item.id).then(() => {
          invalidateCalendarItems();
          queryClient.invalidateQueries({ queryKey: ['items-trash'] });
        });
      });
    });
  }

  useEffect(() => {
    if (patchCalendarItem.isError) invalidateCalendarItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patchCalendarItem.isError]);

  function switchView(next: CalendarView) {
    setView(next);
    window.localStorage.setItem('pa-calendar-view', next);
  }

  function dropOnWeek(sourceId: string, date: string, hour: number | null, minute: number) {
    const item = allItems.find((candidate) => candidate.id === sourceId);
    if (!item) return;
    patchCalendarItem.mutate({ item, payload: buildDragPatch(item, date, hour, minute) });
  }

  function resizeWeekEvent(sourceId: string, durationMinutes: number) {
    const item = allItems.find((candidate) => candidate.id === sourceId);
    if (!item) return;
    patchCalendarItem.mutate({ item, payload: buildResizePatch(item, durationMinutes) });
  }

  function resizeWeekEventStart(sourceId: string, startMinutes: number) {
    const item = allItems.find((candidate) => candidate.id === sourceId);
    if (!item) return;
    const payload = buildStartResizePatch(item, startMinutes);
    if (Object.keys(payload).length > 0) patchCalendarItem.mutate({ item, payload });
  }

  function jumpToWeek(date: string) {
    setWeekOffset(weekOffsetForDate(date));
    switchView('week');
  }

  return (
    <section className="page calendar-page">
      <header className="page-header">
        <div>
          <h1>日程提醒</h1>
          <p>按时间线聚合已设置明确排期时间的事项与日程</p>
        </div>
      </header>

      <div className="calendar-toolbar">
        <div className="segmented-control">
          <button className={view === 'week' ? 'chip active' : 'chip'} type="button" onClick={() => switchView('week')}>
            周视图
          </button>
          <button className={view === 'month' ? 'chip active' : 'chip'} type="button" onClick={() => switchView('month')}>
            月视图
          </button>
          <button className={view === 'list' ? 'chip active' : 'chip'} type="button" onClick={() => switchView('list')}>
            列表
          </button>
        </div>
        {view === 'week' && (
          <div className="segmented-control">
            <button className="chip" type="button" onClick={() => setWeekOffset((offset) => offset - 1)}>
              上一周
            </button>
            <button className={weekOffset === 0 ? 'chip active' : 'chip'} type="button" onClick={() => setWeekOffset(0)}>
              本周
            </button>
            <button className="chip" type="button" onClick={() => setWeekOffset((offset) => offset + 1)}>
              下一周
            </button>
          </div>
        )}
        {view === 'month' && (
          <div className="segmented-control">
            <button className="chip" type="button" onClick={() => setMonthOffset((offset) => offset - 1)}>
              上一月
            </button>
            <button className={monthOffset === 0 ? 'chip active' : 'chip'} type="button" onClick={() => setMonthOffset(0)}>
              本月
            </button>
            <button className="chip" type="button" onClick={() => setMonthOffset((offset) => offset + 1)}>
              下一月
            </button>
          </div>
        )}
        <button
          className={filterOpen || activeFilterCount > 0 ? 'chip active' : 'chip'}
          type="button"
          onClick={() => setFilterOpen((open) => !open)}
        >
          筛选{activeFilterCount > 0 ? ` ${activeFilterCount}` : ''}
        </button>
        <div className="display-menu-wrap">
            <button className={displayOpen ? 'chip active' : 'chip'} type="button" onClick={() => setDisplayOpen((open) => !open)}>
              显示 ▾
            </button>
            {displayOpen && (
              <div className="display-menu">
                <button
                  className="display-menu-item"
                  type="button"
                  onClick={() => {
                    setShowDone((v) => {
                      localStorage.setItem('pa-calendar-show-done', v ? '0' : '1');
                      return !v;
                    });
                  }}
                >
                  <span className="menu-check">{showDone ? '✓' : ''}</span>
                  <span>显示已完成</span>
                </button>
                <button
                  className="display-menu-item"
                  type="button"
                  title="开启后周视图可拖动改期、拉动事件块上下边调整时间"
                  onClick={() => {
                    setDragEnabled((v) => {
                      localStorage.setItem('pa-calendar-drag-enabled', v ? '0' : '1');
                      return !v;
                    });
                  }}
                >
                  <span className="menu-check">{dragEnabled ? '✓' : ''}</span>
                  <span>拖拽改期</span>
                </button>
              </div>
            )}
          </div>
        <div className="toolbar-right">
          <input placeholder="搜索标题、项目或标签" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
      </div>

      {filterOpen && (
        <div className="calendar-filter-panel">
          <div className="segmented-control">
            {(['all', 'work', 'personal'] as CalendarScopeFilter[]).map((filter) => (
              <button className={scopeFilter === filter ? 'chip active' : 'chip'} type="button" key={filter} onClick={() => setScopeFilter(filter)}>
                {filter === 'all' ? '全部' : filter === 'work' ? '工作' : '个人'}
              </button>
            ))}
          </div>
          <QuickFilterBar value={quickFilter} options={calendarQuickFilters} onChange={setQuickFilter} />
          {activeFilterCount > 0 && (
            <button
              className="ghost sm"
              type="button"
              onClick={() => {
                setScopeFilter('all');
                setQuickFilter('all');
              }}
            >
              清除筛选
            </button>
          )}
        </div>
      )}

      {view === 'list' && (
        <div className="work-summary calendar-summary" aria-label="日程提醒概览">
          <span>有具体时间 {timedSchedules.length}</span>
          <span>今天 {todayCount}</span>
          <span>未来 7 天 {weekCount}</span>
          <span>仅有日期 {dateOnlyItems.length}</span>
        </div>
      )}

      {loading && <p className="empty">加载日程中…</p>}
      {error && <p className="error-line">{error}</p>}
      {patchCalendarItem.error && <p className="error-line">{patchCalendarItem.error.message}（已刷新列表，请重试拖拽）</p>}

      {view === 'week' && (
        <>
          {weekEvents.isLoading && <p className="empty">加载周视图…</p>}
          {weekEvents.error && <p className="error-line">{weekEvents.error.message}</p>}
          {weekEvents.data && (
            <WeekGrid
              dates={dates}
              buckets={weekBuckets}
              onOpenItem={(sourceId) => setSelectedId(sourceId)}
              onDropItem={dropOnWeek}
              onResizeItem={resizeWeekEvent}
                onResizeStartItem={resizeWeekEventStart}
                dragEnabled={dragEnabled}
            />
          )}
          <p className="hint">拖拽事项可调整日期或时刻（15 分钟对齐），拖动底缘调整时长；◆ 表示项目里程碑（仅展示）。</p>
        </>
      )}

      {view === 'month' && (
        <>
          {monthEvents.isLoading && <p className="empty">加载月视图…</p>}
          {monthEvents.error && <p className="error-line">{monthEvents.error.message}</p>}
          {monthEvents.data && (
            <MonthGrid
              dates={mDates}
              buckets={monthBuckets}
              monthAnchor={mDates[7]}
              onOpenItem={(sourceId) => setSelectedId(sourceId)}
              onJumpToDate={jumpToWeek}
            />
          )}
          <p className="hint">点击日期格切换至对应周视图；点击事件条查看详情。</p>
        </>
      )}

      {view === 'list' && (
        <div className="calendar-timeline">
          {grouped.map((group) => (
            <section className="calendar-group" key={group.label}>
              <h2>
                {group.label} <span>{group.schedules.length}</span>
              </h2>
              {group.schedules.length === 0 && <p className="empty">暂无有具体时间的事项</p>}
              {group.schedules.map((schedule) => (
                <CalendarScheduleRow
                  schedule={schedule}
                  key={`${schedule.item.id}-${schedule.relation}-${schedule.time}`}
                  onOpen={() => setSelectedId(schedule.item.id)}
                />
              ))}
            </section>
          ))}
        </div>
      )}

      <details className="calendar-date-only">
        <summary>全天 / 未定具体时间 <span>{dateOnlyItems.length}</span></summary>
        {dateOnlyItems.length === 0 && <p className="empty">暂无仅有日期的事项</p>}
        {dateOnlyItems.map((item) => (
          <article className="calendar-date-row" key={item.id}>
            <div>
              <strong>{item.title}</strong>
              <span>{item.scope === 'work' ? '工作' : '个人'} · {dateOnlyLabel(item)} · 补充具体时间后可触发精确提醒</span>
            </div>
            <div className="date-time-actions">
              {dateOnlyTimeOptions(item.scope).map((option) => (
                <button
                  className="ghost sm"
                  type="button"
                  key={option.label}
                  onClick={() => patchCalendarItem.mutate({ item, payload: buildDateOnlyTimePatch(item, option.time) })}
                >
                  {option.label}
                </button>
              ))}
              <button className="ghost sm" type="button" onClick={() => setSelectedId(item.id)}>
                自定义
              </button>
            </div>
          </article>
        ))}
      </details>

      {selected?.scope === 'work' && (
        <WorkItemDrawer
          item={selected}
          projects={projects.data ?? []}
          session={session}
          saving={saveCalendarItem.isPending || patchCalendarItem.isPending}
          error={saveCalendarItem.error?.message ?? patchCalendarItem.error?.message}
          onClose={() => setSelectedId(null)}
          onSave={(draft, reminderTouched, tagIds) =>
            saveCalendarItem.mutate({ item: selected, draft, reminderTouched, tagIds })
          }
          onStatus={(status) => patchCalendarItem.mutate({ item: selected, payload: { status } })}
          onReschedule={(payload) => patchCalendarItem.mutate({ item: selected, payload })}
          onDelete={() => deleteFromDrawer(selected)}
        />
      )}
      {selected?.scope === 'personal' && (
        <PersonalItemDrawer
          item={selected}
          session={session}
          saving={saveCalendarItem.isPending || patchCalendarItem.isPending}
          error={saveCalendarItem.error?.message ?? patchCalendarItem.error?.message}
          onClose={() => setSelectedId(null)}
          onSave={(draft, reminderTouched, tagIds) =>
            saveCalendarItem.mutate({ item: selected, draft, reminderTouched, tagIds })
          }
          onStatus={(status) => patchCalendarItem.mutate({ item: selected, payload: { status } })}
          onReschedule={(payload) => patchCalendarItem.mutate({ item: selected, payload })}
          onDelete={() => deleteFromDrawer(selected)}
        />
      )}
    </section>
  );
}
