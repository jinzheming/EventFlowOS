import { Tag as TagIcon } from 'lucide-react';
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
  onAddTags,
  onCreateTag,
  onExit,
}: {
  count: number;
  busy: boolean;
  error?: string | null;
  tags: Tag[];
  onComplete: () => void;
  onTomorrow: () => void;
  onNextWeek: () => void;
  onArchive: () => void;
  onAddTags: (tagIds: string[]) => void;
  onCreateTag: (name: string, parentId: string | null) => void;
  onExit: () => void;
}) {
  const [tagPickerOpen, setTagPickerOpen] = useState(false);
  const [pickedTagIds, setPickedTagIds] = useState<string[]>([]);

  function togglePicked(tagId: string) {
    setPickedTagIds((prev) => (prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]));
  }

  return (
    <div className="batch-bar" role="toolbar" aria-label="批量操作">
      <span>已选 {count} 条</span>
      <button className="ghost sm" type="button" disabled={busy} onClick={onComplete}>
        完成
      </button>
      <button className="ghost sm" type="button" disabled={busy} onClick={onTomorrow}>
        延至明天
      </button>
      <button className="ghost sm" type="button" disabled={busy} onClick={onNextWeek}>
        延至下周
      </button>
      <button className="ghost sm" type="button" disabled={busy} onClick={onArchive}>
        归档
      </button>
      <button className="ghost sm" type="button" disabled={busy} onClick={() => setTagPickerOpen((open) => !open)}>
        <TagIcon size={14} /> 加标签
      </button>
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
