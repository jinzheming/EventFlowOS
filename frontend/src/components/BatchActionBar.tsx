import { Tag as TagIcon, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Tag } from '../api/client';
import { TagPicker } from './TagPicker';

/** 列表多选模式底部的批量操作条。 */
export function BatchActionBar({
  count,
  busy,
  error,
  tags,
  onComplete,
  onTomorrow,
  onNextWeek,
  onArchive,
  onDelete,
  onAddTags,
  onCreateTag,
  onExit,
  showComplete = true,
  showReschedule = true,
  showArchive = true,
  showTag = true,
}: {
  count: number;
  busy: boolean;
  error?: string | null;
  tags: Tag[];
  onComplete: () => void;
  onTomorrow: () => void;
  onNextWeek: () => void;
  onArchive: () => void;
  onDelete?: () => void;
  onAddTags: (tagIds: string[]) => void;
  onCreateTag: (name: string, parentId: string | null) => void;
  onExit: () => void;
  showComplete?: boolean;
  showReschedule?: boolean;
  showArchive?: boolean;
  showTag?: boolean;
}) {
  const [tagPickerOpen, setTagPickerOpen] = useState(false);
  const [pickedTagIds, setPickedTagIds] = useState<string[]>([]);

  function togglePicked(tagId: string) {
    setPickedTagIds((prev) => (prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]));
  }

  return (
    <div className="batch-bar" role="toolbar" aria-label="批量操作">
      <span>已选 {count} 条</span>
      {showComplete && (
        <button className="ghost sm" type="button" disabled={busy} onClick={onComplete}>
          完成
        </button>
      )}
      {showReschedule && (
        <>
          <button className="ghost sm" type="button" disabled={busy} onClick={onTomorrow}>
            延至明天
          </button>
          <button className="ghost sm" type="button" disabled={busy} onClick={onNextWeek}>
            延至下周
          </button>
        </>
      )}
      {showArchive && (
        <button className="ghost sm" type="button" disabled={busy} onClick={onArchive}>
          归档
        </button>
      )}
      {showTag && (
        <button className="ghost sm" type="button" disabled={busy} onClick={() => setTagPickerOpen((open) => !open)}>
          <TagIcon size={14} /> 加标签
        </button>
      )}
      {onDelete && (
        <button className="ghost sm danger-text" type="button" disabled={busy} onClick={onDelete}>
          <Trash2 size={14} /> 删除
        </button>
      )}
      <button className="ghost sm" type="button" disabled={busy} onClick={onExit}>
        退出多选
      </button>
      {tagPickerOpen && (
        <div className="batch-tag-popover">
          <TagPicker tags={tags} selected={pickedTagIds} onToggle={togglePicked} onCreateTag={onCreateTag} />
          <button
            className="primary"
            type="button"
            disabled={busy || pickedTagIds.length === 0}
            onClick={() => {
              onAddTags(pickedTagIds);
              setTagPickerOpen(false);
              setPickedTagIds([]);
            }}
          >
            应用到 {count} 条
          </button>
        </div>
      )}
      {error && <span className="error-line">{error}</span>}
    </div>
  );
}
