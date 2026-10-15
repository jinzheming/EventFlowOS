import { SaveViewButton, useApplyViewHandoff } from '../components/SavedViews';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { api, Item, ItemHistoryView, Session } from '../api/client';
import { BatchActionBar } from '../components/BatchActionBar';
import { EmptyState, ListState } from '../components/ListState';
import { QuickFilterBar } from '../components/QuickFilterBar';
import { WorkItemCard } from '../components/WorkItemCard';
import { WorkItemDrawer } from '../components/WorkItemDrawer';
import { useHistoryItems } from '../hooks/useHistoryItems';
import { usePatchItem, useSaveItemWithReminder } from '../hooks/useItemActions';
import { useListKeyboard } from '../hooks/useListKeyboard';
import { useToggleDone } from '../hooks/useToggleDone';
import { useUndo } from '../hooks/useUndo';
import { runBatchSequential } from '../lib/batch';
import { filterItemsByQuickFilter, ItemQuickFilter, workQuickFilters, isHighPriority } from '../lib/itemFilters';
import { filterItemsForView, groupHistoryItems, groupWorkItems, summarizeWorkItems } from '../lib/items';
import { ItemListView, itemViewLabels } from '../lib/labels';
import { buildReschedulePatch } from '../lib/reschedule';

export function WorkItemsPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.projects });
  const [view, setView] = useState<ItemListView>('current');
  const [search, setSearch] = useState('');
  const [quickFilter, setQuickFilter] = useState<ItemQuickFilter>('all');
  const [highPriority, setHighPriority] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [displayOpen, setDisplayOpen] = useState(false);
  const historyView: ItemHistoryView | null = view === 'done' || view === 'archived' ? view : null;
  const isHistoryView = historyView !== null;
  const items = useQuery({ queryKey: ['items', 'work'], queryFn: () => api.items('work', true, '', 500), enabled: !isHistoryView });
  const historyItems = useHistoryItems('work', historyView, search);
  useApplyViewHandoff('work', (spec) => {
    setView('current');
    setSearch(spec.search);
    setQuickFilter(spec.quickFilter);
    setHighPriority(spec.highPriority);
  });
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    // 从标签页跳转而来时自动打开对应事项详情
    const pending = window.sessionStorage.getItem('pa-open-item');
    window.sessionStorage.removeItem('pa-open-item');
    return pending;
  });

  const loadedItems = isHistoryView ? historyItems.loadedItems : items.data ?? [];
  const selected = loadedItems.find((item) => item.id === selectedId) ?? null;

  function invalidateWork() {
    queryClient.invalidateQueries({ queryKey: ['items', 'work'] });
    queryClient.invalidateQueries({ queryKey: ['project-items'] });
    queryClient.invalidateQueries({ queryKey: ['calendar'] });
    queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
  }

  const patchWork = usePatchItem(session, (item) => {
    setSelectedId(item.id);
    invalidateWork();
  });

  const saveWork = useSaveItemWithReminder(session, (item) => {
    setSelectedId(item.id);
    invalidateWork();
  });

  const archiveWork = useMutation({
    mutationFn: (item: Item) => api.archiveItem(session.csrf_token, item.id),
    onSuccess: () => {
      setSelectedId(null);
      invalidateWork();
    },
  });

  const restoreWork = useMutation({
    mutationFn: (item: Item) => api.restoreItem(session.csrf_token, item.id),
    onSuccess: (item) => {
      setSelectedId(item.id);
      invalidateWork();
    },
  });

  const projectById = useMemo(
    () => new Map((projects.data ?? []).map((project) => [project.id, project])),
    [projects.data],
  );
  const visibleItems = useMemo(() => {
    if (isHistoryView) return historyItems.visibleItems;
    const baseItems = filterItemsForView(items.data ?? [], view, search, projectById);
    return filterItemsByQuickFilter(baseItems, quickFilter).filter((item) => !highPriority || isHighPriority(item));
  }, [historyItems.visibleItems, isHistoryView, items.data, projectById, search, view, quickFilter, highPriority]);
  const grouped = useMemo(
    () => (historyView ? groupHistoryItems(visibleItems, historyView) : groupWorkItems(visibleItems)),
    [historyView, visibleItems],
  );
  const currentItems = useMemo(() => (items.data ?? []).filter((item) => !item.archived_at), [items.data]);
  const workStats = useMemo(() => summarizeWorkItems(currentItems), [currentItems]);

  const undo = useUndo();
  const toggle = useToggleDone(session, 'work');

  // 批量操作：多选模式 + 逐条调用既有单 item API（乐观锁版本来自列表缓存）
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchError, setBatchError] = useState<string | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const tags = useQuery({ queryKey: ['tags'], queryFn: api.tags, enabled: selectMode });

  const createTag = useMutation({
    mutationFn: (input: { name: string; parentId: string | null }) =>
      api.createTag(session.csrf_token, { name: input.name, parent_id: input.parentId ?? undefined }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tags'] }),
  });

  const selectedItems = useMemo(
    () => loadedItems.filter((item) => selectedIds.has(item.id)),
    [loadedItems, selectedIds],
  );

  function toggleSelect(itemId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }

  function exitSelectMode() {
    setSelectMode(false);
    setSelectedIds(new Set());
    setBatchError(null);
  }

  async function runBatch(
    label: string,
    targets: Item[],
    action: (item: Item) => Promise<unknown>,
    revert: (item: Item) => Promise<unknown>,
    onAfterChange?: () => void,
  ) {
    if (targets.length === 0) return;
    setBatchBusy(true);
    setBatchError(null);
    const { succeeded, failed } = await runBatchSequential(targets, action);
    setBatchBusy(false);
    invalidateWork();
    onAfterChange?.();
    if (failed.length > 0) {
      setBatchError(`${failed.length} 条失败（可能已被并发修改），已保留选中`);
      setSelectedIds(new Set(failed.map((item) => item.id)));
      return;
    }
    undo.pushUndo(`${label} ${succeeded.length} 条`, () => {
      void runBatchSequential(succeeded, revert).then(() => {
        invalidateWork();
        onAfterChange?.();
      });
    });
    exitSelectMode();
  }

  const batchComplete = () =>
    runBatch(
      '已批量完成',
      selectedItems.filter((item) => item.status !== 'done' && !item.archived_at),
      (item) => api.patchItem(session.csrf_token, item, { status: 'done' }),
      (item) => api.patchItem(session.csrf_token, item, { status: item.status }),
    );

  function runBatchReschedule(option: 'tomorrow' | 'next_week') {
    return runBatch(
      option === 'tomorrow' ? '已延至明天' : '已延至下周',
      selectedItems.filter((item) => !item.archived_at),
      (item) => api.patchItem(session.csrf_token, item, buildReschedulePatch(option)),
      (item) =>
        api.patchItem(session.csrf_token, item, {
          all_day: item.all_day,
          start_at: item.start_at,
          due_at: item.due_at,
          start_date: item.start_date,
          due_date: item.due_date,
        }),
    );
  }

  const batchArchive = () =>
    runBatch(
      '已批量归档',
      selectedItems.filter((item) => !item.archived_at),
      (item) => api.archiveItem(session.csrf_token, item.id),
      (item) => api.restoreItem(session.csrf_token, item.id),
    );

  const batchAddTags = (tagIds: string[]) =>
    runBatch(
      '已批量加标签',
      selectedItems,
      (item) =>
        api.patchItem(session.csrf_token, item, {
          tag_ids: [...new Set([...item.tags.map((tag) => tag.id), ...tagIds])],
        }),
      (item) => api.patchItem(session.csrf_token, item, { tag_ids: item.tags.map((tag) => tag.id) }),
    );

  const batchDelete = () =>
    runBatch(
      '已批量删除',
      selectedItems,
      (item) => api.deleteItem(session.csrf_token, item.id),
      (item) => api.restoreDeletedItem(session.csrf_token, item.id),
      () => {
        setSelectedId(null);
        queryClient.invalidateQueries({ queryKey: ['items-trash'] });
      },
    );

  function loadMoreHistory() {
    historyItems.loadMore();
  }

  function toggleWithUndo(item: Item) {
    const next = item.status === 'done' ? 'planned' : 'done';
    const previousStatus = item.status;
    toggle.mutate(
      { item, next },
      {
        onSuccess: (updated) => {
          if (next === 'done') {
            undo.pushUndo(`已完成「${item.title}」`, () => toggle.mutate({ item: updated, next: previousStatus }));
          }
        },
      },
    );
  }

  function archiveWithUndo(item: Item) {
    archiveWork.mutate(item, {
      onSuccess: () => undo.pushUndo(`已归档「${item.title}」`, () => restoreWork.mutate(item)),
    });
  }

  // 软删除：进回收站（设置页），撤销即恢复
  function deleteWithUndo(item: Item) {
    void api.deleteItem(session.csrf_token, item.id).then(() => {
      setSelectedId(null);
      invalidateWork();
      queryClient.invalidateQueries({ queryKey: ['items-trash'] });
      undo.pushUndo(`已删除「${item.title}」（回收站可恢复）`, () => {
        void api.restoreDeletedItem(session.csrf_token, item.id).then(() => {
          invalidateWork();
          queryClient.invalidateQueries({ queryKey: ['items-trash'] });
        });
      });
    });
  }

  // 周期事项「跳过本次」：标记完成让后端生成下一次；撤销则恢复为待处理
  // （撤销不会删除后端已生成的下一次事项，属于尽力而为的回滚）。
  function skipWithUndo(item: Item) {
    patchWork.mutate(
      { item, payload: { status: 'done' } },
      {
        onSuccess: (updated) => {
          setSelectedId(updated.id);
          invalidateWork();
          undo.pushUndo(`已跳过「${item.title}」`, () => patchWork.mutate({ item: updated, payload: { status: 'planned' } }));
        },
      },
    );
  }

  const flatItems = useMemo(() => grouped.flatMap((group) => group.items), [grouped]);
  const { focusIndex } = useListKeyboard(
    flatItems,
    { onOpen: (item) => setSelectedId(item.id), onToggle: toggleWithUndo },
    !selected,
  );

  const workFilterCount = (quickFilter !== 'all' ? 1 : 0) + (highPriority ? 1 : 0);
  const listError = isHistoryView ? historyItems.query.error : items.error;
  const listErrorMessage = listError ? (listError instanceof Error ? listError.message : String(listError)) : null;
  const retryList = () => {
    if (isHistoryView) void historyItems.query.refetch();
    else void items.refetch();
  };

  return (
    <section className="page work-page">
      <header className="page-header">
        <div>
          <h1>工作事项</h1>
          <p>
            {isHistoryView
              ? `已显示 ${historyItems.visibleCount}/${historyItems.totalCount} 条 · 按周展示`
              : `${visibleItems.length} 条 · 今天/逾期 ${workStats.today} · 等待 ${workStats.waiting} · 未排期 ${workStats.unscheduled} · 新建 ⌘K`}
          </p>
        </div>
      </header>

      <div className="list-controls">
        <div className="segmented-control">
          {(['current', 'done', 'archived'] as ItemListView[]).map((option) => (
            <button className={view === option ? 'chip active' : 'chip'} type="button" key={option} onClick={() => setView(option)}>
              {itemViewLabels[option]}
            </button>
          ))}
        </div>
        {view === 'current' && (
          <button
            className={filterOpen || workFilterCount > 0 ? 'chip active' : 'chip'}
            type="button"
            onClick={() => setFilterOpen((open) => !open)}
          >
            筛选{workFilterCount > 0 ? ` ${workFilterCount}` : ''}
          </button>
        )}
        <div className="toolbar-right">
          <input placeholder="搜索标题、备注、项目或标签" value={search} onChange={(event) => setSearch(event.target.value)} />
          <div className="display-menu-wrap">
            <button className={displayOpen || selectMode ? 'chip active' : 'chip'} type="button" onClick={() => setDisplayOpen((open) => !open)}>
              显示 ▾
            </button>
            {displayOpen && (
              <div className="display-menu">
                <button className="display-menu-item" type="button" onClick={() => (selectMode ? exitSelectMode() : setSelectMode(true))}>
                  <span className="menu-check">{selectMode ? '✓' : ''}</span>
                  <span>多选模式</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {view === 'current' && filterOpen && (
        <div className="calendar-filter-panel">
          <QuickFilterBar value={quickFilter} options={workQuickFilters} onChange={setQuickFilter} />
          <button className={highPriority ? 'chip active' : 'chip'} type="button" onClick={() => setHighPriority(!highPriority)}>
            高优
          </button>
          {workFilterCount > 0 && (
            <button
              className="ghost sm"
              type="button"
              onClick={() => {
                setQuickFilter('all');
                setHighPriority(false);
              }}
            >
              清除筛选
            </button>
          )}
          <SaveViewButton session={session} spec={{ page: 'work', quickFilter, highPriority, search }} />
        </div>
      )}

      <ListState loading={isHistoryView ? historyItems.query.isLoading : items.isLoading} error={listErrorMessage} onRetry={retryList}>
        {visibleItems.length === 0 ? (
          <EmptyState
            filtered={Boolean(search.trim()) || (view === 'current' && quickFilter !== 'all') || view !== 'current'}
            onClearFilters={() => {
              setSearch('');
              setQuickFilter('all');
              setView('current');
            }}
          >
            {view === 'current' ? '暂无工作事项，按 ⌘K 快速添加第一条' : view === 'done' ? '暂无已完成事项' : '暂无归档事项'}
          </EmptyState>
        ) : (
          <div className={isHistoryView ? 'work-board history-list' : 'work-board'}>
            {grouped.map((group) => (
              <section className={isHistoryView ? 'work-group history-group' : 'work-group'} key={group.label}>
                <h2>
                  {isHistoryView ? <span className="history-week-label">{group.label}</span> : group.label}
                  <span>{group.items.length} 条</span>
                </h2>
                {group.items.length === 0 && <p className="empty">暂无事项</p>}
                {group.items.map((item) => (
                  <WorkItemCard
                    item={item}
                    session={session}
                    project={item.project_id ? projectById.get(item.project_id) : undefined}
                    key={item.id}
                    selected={item.id === selectedId}
                    focused={flatItems[focusIndex]?.id === item.id}
                    selectMode={selectMode}
                    checked={selectedIds.has(item.id)}
                    onCheck={() => toggleSelect(item.id)}
                    onOpen={() => (selectMode ? toggleSelect(item.id) : setSelectedId(item.id))}
                    onToggleDone={() => toggleWithUndo(item)}
                    onSkip={() => skipWithUndo(item)}
                    onArchive={() => archiveWithUndo(item)}
                    onRestore={() => restoreWork.mutate(item)}
                  />
                ))}
              </section>
            ))}
            {isHistoryView && historyItems.hasMore && (
              <div className="history-load-more">
                <button className="secondary" type="button" disabled={historyItems.query.isFetchingNextPage} onClick={loadMoreHistory}>
                  {historyItems.query.isFetchingNextPage ? '加载中…' : '加载更多'}
                </button>
                <span>
                  已显示 {historyItems.visibleCount}/{historyItems.totalCount} 条
                </span>
              </div>
            )}
          </div>
        )}
      </ListState>

      {selectMode && selectedItems.length > 0 && (
        <BatchActionBar
          count={selectedItems.length}
          busy={batchBusy}
          error={batchError}
          tags={tags.data ?? []}
          onComplete={batchComplete}
          onTomorrow={() => runBatchReschedule('tomorrow')}
          onNextWeek={() => runBatchReschedule('next_week')}
          onArchive={batchArchive}
          onDelete={isHistoryView ? batchDelete : undefined}
          onAddTags={batchAddTags}
          onCreateTag={(name, parentId) => createTag.mutate({ name, parentId })}
          onExit={exitSelectMode}
          showComplete={!isHistoryView}
          showReschedule={!isHistoryView}
          showArchive={view !== 'archived'}
        />
      )}

      {selected && (
        <WorkItemDrawer
          item={selected}
          projects={projects.data ?? []}
          session={session}
          saving={saveWork.isPending || patchWork.isPending}
          error={saveWork.error?.message ?? patchWork.error?.message}
          onClose={() => setSelectedId(null)}
          onSave={(draft, reminderTouched, tagIds) => saveWork.mutate({ item: selected, draft, reminderTouched, tagIds })}
          onStatus={(status) => patchWork.mutate({ item: selected, payload: { status } })}
          onReschedule={(payload) => patchWork.mutate({ item: selected, payload })}
          onDelete={() => deleteWithUndo(selected)}
        />
      )}
    </section>
  );
}
