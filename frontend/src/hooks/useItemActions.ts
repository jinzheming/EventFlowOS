import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, Item, ItemPayload, Session } from '../api/client';
import {
  PersonalDraft,
  WorkDraft,
  buildPersonalPatch,
  buildWorkPatch,
  hasDraftSchedule,
  hasPersonalDraftSchedule,
} from '../lib/drafts';
import { reminderTiming } from '../lib/workSchedule';

export type SaveItemArgs = {
  item: Item;
  draft: WorkDraft | PersonalDraft;
  reminderTouched: boolean;
  /** null = 标签未改动;非 null = 整体替换该事项的标签集合 */
  tagIds?: string[] | null;
};

export function useSaveItemWithReminder(session: Session, onSaved: (item: Item) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ item, draft, reminderTouched, tagIds }: SaveItemArgs) => {
      const payload: ItemPayload =
        item.scope === 'work' ? buildWorkPatch(draft as WorkDraft) : buildPersonalPatch(draft as PersonalDraft);
      if (tagIds !== undefined && tagIds !== null) {
        payload.tag_ids = tagIds;
      }
      const updated = await api.patchItem(session.csrf_token, item, payload);
      if (reminderTouched) {
        const hasSchedule = item.scope === 'work' ? hasDraftSchedule(draft as WorkDraft) : hasPersonalDraftSchedule(draft as PersonalDraft);
        if (hasSchedule && draft.reminder_enabled) {
          await api.putReminder(session.csrf_token, item.id, {
            timing: reminderTiming(draft),
            offset_minutes: draft.reminder_offset,
            timezone: session.timezone,
            external_enabled: draft.reminder_external,
          });
        } else {
          await api.deleteReminder(session.csrf_token, item.id);
        }
        queryClient.invalidateQueries({ queryKey: ['item-reminder', item.id] });
      }
      return updated;
    },
    onSuccess: onSaved,
  });
}

export type PatchItemArgs = {
  item: Item;
  payload: ItemPayload;
};

export function usePatchItem(session: Session, onSaved: (item: Item) => void) {
  return useMutation({
    mutationFn: ({ item, payload }: PatchItemArgs) => api.patchItem(session.csrf_token, item, payload),
    onSuccess: onSaved,
  });
}
