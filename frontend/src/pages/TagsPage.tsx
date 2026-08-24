import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Pin, Plus, X } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { api, Item, Scope, Session, Tag } from '../api/client';
import { ItemRowShell, RowPriorityMark, RowSegments, RowTimeSlot, RowWaitingMark, rowTooltip } from '../components/ItemRow';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { matchesItemSearch } from '../lib/items';
import { scopeLabel } from '../lib/labels';

type ScopeFilter = 'all' | Scope;

const TAG_COLORS = ['#4F46E5', '#CA8A04', '#B45309', '#1D4ED8', '#7C3AED', '#BE185D', '#64748B'];

export function TagsPage({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const tags = useQuery({ queryKey: ['tags'], queryFn: api.tags });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [includeDone, setIncludeDone] = useState(false);
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all');
  const [recursive, setRecursive] = useState(true);
  const [itemSearch, setItemSearch] = useState('');
  const [createParentId, setCreateParentId] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Tag | null>(null);
  const [confirming, setConfirming] = useState<Tag | null>(null);
  const [displayOpen, setDisplayOpen] = useState(false);

  const roots = tags.data ?? [];

  useEffect(() => {
    const wanted = sessionStorage.getItem('pa-open-tag');
    if (wanted) {
      sessionStorage.removeItem('pa-open-tag');
      setSelectedId(wanted);
      return;
    }
    if (!selectedId && roots.length > 0) setSelectedId(roots[0].id);
  }, [roots, selectedId]);

  const items = useQuery({
    queryKey: ['tag-items', selectedId, includeDone, scopeFilter, recursive],
    queryFn: () =>
      api.tagItems(selectedId as string, {
        include_done: includeDone,
        scope: scopeFilter === 'all' ? undefined : scopeFilter,
        recursive,
      }),
    enabled: Boolean(selectedId),
  });
  const visibleItems = useMemo(
    () => (items.data ?? []).filter((item) => matchesItemSearch(item, itemSearch)),
    [items.data, itemSearch],
  );

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['tags'] });
    queryClient.invalidateQueries({ queryKey: ['tag-items'] });
  }

  const createTag = useMutation({
    mutationFn: (input: { name: string; color: string; parent_id: string | null }) =>
      api.createTag(session.csrf_token, input),
    onSuccess: invalidate,
  });

  const renameTag = useMutation({
    mutationFn: (input: { tag: Tag; name: string; color: string }) =>
      api.patchTag(session.csrf_token, input.tag.id, { name: input.name, color: input.color }),
    onSuccess: invalidate,
  });

  const pinTag = useMutation({
    mutationFn: ({ tag, pinned }: { tag: Tag; pinned: boolean }) => api.patchTag(session.csrf_token, tag.id, { pinned }),
    onSuccess: invalidate,
  });

  const deleteTag = useMutation({
    mutationFn: (tag: Tag) => api.deleteTag(session.csrf_token, tag.id),
    onSuccess: () => {
      setSelectedId(null);
      invalidate();
    },
  });

  const toggleDone = useMutation({
    mutationFn: (item: Item) =>
      api.patchItem(session.csrf_token, item, { status: item.status === 'done' ? 'planned' : 'done' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tag-items'] }),
  });

  function openItem(item: Item) {
    window.sessionStorage.setItem('pa-open-item', item.id);
    window.location.hash = item.scope === 'work' ? '/work' : '/personal';
  }



  return (
    <section className="page tags-page">
      <header className="page-header">
        <div>
          <h1>标签</h1>
          <p>{roots.length} 个顶层标签 · 两级嵌套 · 工作/个人共用</p>
        </div>
        <button className="primary" type="button" onClick={() => { setCreateOpen(true); setCreateParentId(''); }}>
          <Plus size={16} /> 新建标签
        </button>
      </header>

      <div className="tags-layout">
        <aside className="tag-tree">
          {roots.length === 0 && <p className="empty">暂无标签，点击右上角新建</p>}
          {roots.map((root) => (
            <div className="tag-tree-node" key={root.id}>
              <div
                className={`tag-tree-row ${selectedId === root.id ? 'active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedId(root.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setSelectedId(root.id);
                  }
                }}
              >
                <span className="tag-dot" style={{ background: root.color }} />
                <span className="tag-tree-name">{root.name}</span>
                {root.pinned && <Pin size={11} className="tag-pin-mark" />}
                <span className="tag-tree-count">{root.item_count}</span>
                <span className="tag-tree-ops">
                  <button
                    className="ghost sm"
                    type="button"
                    title="新建子标签"
                    onClick={(event) => {
                      event.stopPropagation();
                      setCreateOpen(true);
                      setCreateParentId(root.id);
                    }}
                  >
                    <Plus size={12} />
                  </button>
                  <button
                    className="ghost sm"
                    type="button"
                    title="编辑（重命名/固定/删除）"
                    onClick={(event) => {
                      event.stopPropagation();
                      setEditing(root);
                    }}
                  >
                    <Pencil size={12} />
                  </button>
                </span>
              </div>
              {root.children.map((child) => (
                <div className="tag-tree-node child" key={child.id}>
                  <div
                    className={`tag-tree-row ${selectedId === child.id ? 'active' : ''}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(child.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setSelectedId(child.id);
                      }
                    }}
                  >
                    <span className="tag-dot" style={{ background: child.color }} />
                    <span className="tag-tree-name">{child.name}</span>
                    {child.pinned && <Pin size={11} className="tag-pin-mark" />}
                    <span className="tag-tree-count">{child.item_count}</span>
                    <span className="tag-tree-ops">
                      <button
                        className="ghost sm"
                        type="button"
                        title="编辑（重命名/固定/删除）"
                        onClick={(event) => {
                          event.stopPropagation();
                          setEditing(child);
                        }}
                      >
                        <Pencil size={12} />
                      </button>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </aside>

        <main className="tags-items">
          {!selectedId ? (
            <p className="empty">从左侧选择标签查看关联事项</p>
          ) : (
            <>
              <div className="list-controls tag-item-controls">
                <div className="segmented-control">
                  {(['all', 'work', 'personal'] as ScopeFilter[]).map((option) => (
                    <button
                      className={scopeFilter === option ? 'chip active' : 'chip'}
                      type="button"
                      key={option}
                      onClick={() => setScopeFilter(option)}
                    >
                      {option === 'all' ? '全部' : scopeLabel(option)}
                    </button>
                  ))}
                </div>
                <div className="toolbar-right">
                  <input placeholder="搜索该标签下事项" value={itemSearch} onChange={(event) => setItemSearch(event.target.value)} />
                  <div className="display-menu-wrap">
                    <button className={displayOpen ? 'chip active' : 'chip'} type="button" onClick={() => setDisplayOpen((open) => !open)}>
                      显示 ▾
                    </button>
                    {displayOpen && (
                      <div className="display-menu">
                        <button className="display-menu-item" type="button" onClick={() => setIncludeDone((v) => !v)}>
                          <span className="menu-check">{includeDone ? '✓' : ''}</span>
                          <span>显示已完成</span>
                        </button>
                        <button className="display-menu-item" type="button" onClick={() => setRecursive((v) => !v)}>
                          <span className="menu-check">{recursive ? '✓' : ''}</span>
                          <span>包含子标签</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              {items.isLoading && <p className="empty">加载中…</p>}
              {!items.isLoading && visibleItems.length === 0 && <p className="empty">当前标签下暂无匹配事项</p>}
              {visibleItems.map((item) => (
                <ItemRowShell
                  key={item.id}
                  className="tags-item-row"
                  done={item.status === 'done'}
                  tooltip={rowTooltip(item)}
                  onOpen={() => openItem(item)}
                  check={{ done: item.status === 'done', onToggle: () => toggleDone.mutate(item) }}
                  flow={
                    <>
                      <span className="row-scope">{scopeLabel(item.scope)}</span>
                      <strong className="row-title">{item.title}</strong>
                      <RowPriorityMark item={item} />
                      <RowWaitingMark item={item} />
                      <RowSegments item={item} />
                    </>
                  }
                  timeslot={<RowTimeSlot item={item} />}
                />
              ))}
            </>
          )}
        </main>
      </div>

      {createOpen && (
        <TagFormModal
          mode="create"
          parentId={createParentId}
          roots={roots}
          submitting={createTag.isPending}
          error={createTag.error?.message}
          onClose={() => setCreateOpen(false)}
          onSubmit={(name, color) =>
            createTag.mutate({ name, color, parent_id: createParentId || null })
          }
        />
      )}
      {editing && (
        <TagFormModal
          mode="rename"
          tag={editing}
          roots={roots}
          submitting={renameTag.isPending}
          error={renameTag.error?.message}
          onClose={() => setEditing(null)}
          onSubmit={(name, color) => renameTag.mutate({ tag: editing, name, color })}
          onTogglePin={(tag) => pinTag.mutate({ tag, pinned: !tag.pinned })}
          onRequestDelete={(tag) => {
            setEditing(null);
            setConfirming(tag);
          }}
        />
      )}
      {confirming && (
        <div className="modal-backdrop" role="presentation" onClick={() => setConfirming(null)}>
          <div className="modal-panel confirm-panel" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <header className="panel-header">
              <div>
                <p className="eyebrow">Tag</p>
                <h2>删除标签</h2>
              </div>
            </header>
            <p>
              确定删除标签「{confirming.name}」？
              {(confirming.children?.length ?? 0) > 0
                ? `其 ${confirming.children!.length} 个子标签会一并删除，并从所有事项中移除。`
                : '该标签会从所有事项中移除。'}
            </p>
            <footer className="panel-actions">
              <button className="secondary" type="button" onClick={() => setConfirming(null)}>
                取消
              </button>
              <button
                className="primary danger"
                type="button"
                disabled={deleteTag.isPending}
                onClick={() => {
                  deleteTag.mutate(confirming);
                  setConfirming(null);
                }}
              >
                删除
              </button>
            </footer>
          </div>
        </div>
      )}
    </section>
  );
}

function TagFormModal({
  mode,
  tag,
  parentId,
  roots,
  submitting,
  error,
  onClose,
  onSubmit,
  onTogglePin,
  onRequestDelete,
}: {
  mode: 'create' | 'rename';
  tag?: Tag;
  parentId?: string;
  roots: Tag[];
  submitting: boolean;
  error?: string;
  onClose: () => void;
  onSubmit: (name: string, color: string) => void;
  onTogglePin?: (tag: Tag) => void;
  onRequestDelete?: (tag: Tag) => void;
}) {
  const [name, setName] = useState(mode === 'rename' ? (tag?.name ?? '') : '');
  const [color, setColor] = useState(mode === 'rename' ? (tag?.color ?? TAG_COLORS[0]) : TAG_COLORS[0]);
  const panelRef = useRef<HTMLFormElement>(null);
  useDialogA11y(panelRef, onClose);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) onSubmit(name.trim(), color);
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tag-modal-title"
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
        onSubmit={submit}
      >
        <header className="panel-header">
          <div>
            <p className="eyebrow">Tag</p>
            <h2 id="tag-modal-title">{mode === 'create' ? (parentId ? '新建子标签' : '新建标签') : '重命名标签'}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭">
            <X size={16} />
          </button>
        </header>
        <label>
          标签名
          <input data-autofocus value={name} maxLength={50} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          颜色
          <div className="tag-color-row">
            {TAG_COLORS.map((candidate) => (
              <button
                type="button"
                key={candidate}
                className={`tag-color-swatch ${color === candidate ? 'active' : ''}`}
                style={{ background: candidate }}
                onClick={() => setColor(candidate)}
                aria-label={candidate}
              />
            ))}
          </div>
        </label>
        {mode === 'rename' && tag && (
          <div className="tag-modal-extras">
            <button className="ghost sm" type="button" onClick={() => onTogglePin?.(tag)}>
              <Pin size={13} /> {tag.pinned ? '从侧栏取消固定' : '固定到侧栏'}
            </button>
            <button className="ghost sm danger-text" type="button" onClick={() => onRequestDelete?.(tag)}>
              删除标签
            </button>
          </div>
        )}
        {mode === 'create' && parentId && (
          <p className="hint">
            将创建为「{roots.find((root) => root.id === parentId)?.name}」的子标签（仅支持两层）
          </p>
        )}
        {error && <p className="error-line">{error}</p>}
        <footer className="panel-actions">
          <button className="secondary" type="button" onClick={onClose}>
            取消
          </button>
          <button className="primary" type="submit" disabled={!name.trim() || submitting}>
            保存
          </button>
        </footer>
      </form>
    </div>
  );
}
