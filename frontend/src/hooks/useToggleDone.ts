import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, Item, ItemStatus, Scope, Session } from '../api/client';

type ToggleArgs = {
  item: Item;
  next: ItemStatus;
};

type ToggleContext = {
  previous: Item[] | undefined;
};

/**
 * Optimistic status toggle for one scope's item list.
 * Rolls the cache back on error and refetches on settle.
 */
export function useToggleDone(session: Session, scope: Scope, onSuccess?: (updated: Item, args: ToggleArgs) => void) {
  const queryClient = useQueryClient();
  return useMutation<Item, Error, ToggleArgs, ToggleContext>({
    mutationFn: ({ item, next }) => api.patchItem(session.csrf_token, item, { status: next }),
    onMutate: async ({ item, next }) => {
      await queryClient.cancelQueries({ queryKey: ['items', scope] });
      const previous = queryClient.getQueryData<Item[]>(['items', scope]);
      queryClient.setQueryData<Item[]>(['items', scope], (old) =>
        old?.map((entry) => (entry.id === item.id ? { ...entry, status: next } : entry)),
      );
      return { previous };
    },
    onError: (_error, _args, context) => {
      if (context?.previous) queryClient.setQueryData(['items', scope], context.previous);
    },
    onSuccess: (updated, args) => {
      onSuccess?.(updated, args);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['items', scope] });
      queryClient.invalidateQueries({ queryKey: ['reminder-health'] });
    },
  });
}
