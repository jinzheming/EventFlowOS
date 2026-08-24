import { useState } from 'react';
import { Tag } from '../api/client';

/**
 * 标签多选器:两层标签树展示,点选/取消;支持行内新建标签。
 */
export function TagPicker({
  tags,
  selected,
  onToggle,
  onCreateTag,
}: {
  tags: Tag[];
  selected: string[];
  onToggle: (tagId: string) => void;
  onCreateTag: (name: string, parentId: string | null) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [parentId, setParentId] = useState('');
  const roots = tags.filter((tag) => !tag.parent_id);

  function chipClass(tag: Tag) {
    return selected.includes(tag.id) ? 'tag-chip on' : 'tag-chip';
  }

  function submitCreate() {
    const trimmed = name.trim();
    if (!trimmed) return;
    onCreateTag(trimmed, parentId || null);
    setName('');
    setParentId('');
    setCreating(false);
  }

  return (
    <div className="tag-picker">
      {roots.length === 0 && <p className="hint">还没有标签,先新建一个吧</p>}
      {roots.map((root) => (
        <div className="tag-picker-group" key={root.id}>
          <button type="button" className={chipClass(root)} onClick={() => onToggle(root.id)}>
            <span className="tag-dot" style={{ background: root.color }} />
            {root.name}
          </button>
          <div className="tag-picker-children">
            {root.children.map((child) => (
              <button type="button" className={`${chipClass(child)} tag-picker-child`} key={child.id} onClick={() => onToggle(child.id)}>
                <span className="tag-dot" style={{ background: child.color }} />
                {child.name}
              </button>
            ))}
          </div>
        </div>
      ))}
      {!creating ? (
        <button type="button" className="ghost sm" onClick={() => setCreating(true)}>
          + 新建标签
        </button>
      ) : (
        <div className="tag-picker-new">
          <input
            autoFocus
            value={name}
            placeholder="标签名"
            maxLength={50}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                submitCreate();
              }
            }}
          />
          <select value={parentId} onChange={(event) => setParentId(event.target.value)} title="父级标签">
            <option value="">顶层标签</option>
            {roots.map((root) => (
              <option value={root.id} key={root.id}>
                {root.name}
              </option>
            ))}
          </select>
          <button type="button" className="primary" disabled={!name.trim()} onClick={submitCreate}>
            创建
          </button>
          <button type="button" className="secondary" onClick={() => setCreating(false)}>
            取消
          </button>
        </div>
      )}
    </div>
  );
}
