import { useInfiniteQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { api, ItemHistoryView, Scope } from '../api/client';
import { HISTORY_BATCH_SIZE, historyWindowForItems } from '../lib/items';

export function useHistoryItems(scope: Scope, view: ItemHistoryView | null, search: string) {
  const [minimumCount, setMinimumCount] = useState(HISTORY_BATCH_SIZE);
  const enabled = view !== null;
  const query = useInfiniteQuery({
    queryKey: ['items', scope, 'history', view, search],
    queryFn: ({ pageParam }) => api.historyItems(scope, view ?? 'done', search, HISTORY_BATCH_SIZE, pageParam),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.offset + lastPage.items.length : undefined),
    enabled,
  });
  const { fetchNextPage, hasNextPage, isFetchingNextPage } = query;

  useEffect(() => setMinimumCount(HISTORY_BATCH_SIZE), [view, search]);

  const loadedItems = useMemo(() => query.data?.pages.flatMap((page) => page.items) ?? [], [query.data]);
  const window = useMemo(
    () => (view ? historyWindowForItems(loadedItems, view, minimumCount) : null),
    [loadedItems, minimumCount, view],
  );

  useEffect(() => {
    if (!enabled || !window || !hasNextPage || isFetchingNextPage) return;
    if (window.visibleCount >= loadedItems.length) void fetchNextPage();
  }, [enabled, fetchNextPage, hasNextPage, isFetchingNextPage, loadedItems.length, window]);

  function loadMore() {
    if (!window) return;
    setMinimumCount((count) => Math.max(count + HISTORY_BATCH_SIZE, window.visibleCount + HISTORY_BATCH_SIZE));
    if (!window.hasMore && hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }

  const totalCount = query.data?.pages[0]?.total ?? window?.totalCount ?? 0;
  const visibleCount = window?.visibleCount ?? 0;
  const hasMore = Boolean(window && (window.hasMore || visibleCount < totalCount || hasNextPage));

  return {
    query,
    loadedItems,
    visibleItems: window?.items ?? [],
    totalCount,
    visibleCount,
    hasMore,
    loadMore,
  };
}
