import type { Item, Session } from '../api/client';
import { ItemRowShell, RowPriorityMark, RowSegments, RowTimeSlot, RowWaitingMark, rowTooltip } from './ItemRow';
import { RowFocusButton } from './RowFocusButton';

export function PersonalItemRow({
  item,
  session,
  selected,
  focused,
  selectMode,
  checked,
  onCheck,
  onOpen,
  onToggleDone,
  onSkip,
  onArchive,
  onRestore,
}: {
  item: Item;
  session?: Session;
  selected: boolean;
  focused?: boolean;
  selectMode?: boolean;
  checked?: boolean;
  onCheck?: () => void;
  onOpen: () => void;
  onToggleDone: () => void;
  onSkip: () => void;
  onArchive: () => void;
  onRestore: () => void;
}) {
  const done = item.status === 'done';
  return (
    <ItemRowShell
      className="personal-row"
      selected={selected}
      focused={focused}
      done={done}
      tooltip={rowTooltip(item)}
      onOpen={onOpen}
      selectCheck={selectMode && onCheck ? { checked: checked ?? false, onCheck } : undefined}
      check={{ done, onToggle: onToggleDone }}
      flow={
        <>
          <strong className="row-title">{item.title}</strong>
          <RowPriorityMark item={item} />
          <RowWaitingMark item={item} />
          <RowSegments item={item} />
        </>
      }
      timeslot={<RowTimeSlot item={item} />}
      ops={
        <>
          {session && <RowFocusButton itemId={item.id} session={session} />}
          {item.recurrence_freq && !done && item.status !== 'cancelled' && (
            <button
              className="ghost sm"
              type="button"
              title="结束本次并自动生成下一次（今天不做也不挂逾期）"
              onClick={(event) => {
                event.stopPropagation();
                onSkip();
              }}
            >
              跳过本次
            </button>
          )}
          <button
            className="ghost sm"
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              item.archived_at ? onRestore() : onArchive();
            }}
          >
            {item.archived_at ? '恢复' : '归档'}
          </button>
        </>
      }
    />
  );
}
