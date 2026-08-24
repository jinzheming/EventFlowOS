import { useQuery } from '@tanstack/react-query';
import { Search, X } from 'lucide-react';
import { KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { api, Item } from '../api/client';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { scheduleBadge } from '../lib/dates';
import { scopeLabel } from '../lib/labels';

/** 全局搜索（⌘P）：服务端搜索工作+个人事项的标题/备注，Enter 打开选中结果。 */
export function SearchDialog({ onClose, onOpenItem }: { onClose: () => void; onOpenItem: (item: Item) => void }) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogA11y(panelRef, onClose);
  const [input, setInput] = useState('');
  const [term, setTerm] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const handle = window.setTimeout(() => setTerm(input.trim()), 250);
    return () => window.clearTimeout(handle);
  }, [input]);

  const work = useQuery({
    queryKey: ['search', 'work', term],
    queryFn: () => api.items('work', false, term),
    enabled: term.length > 0,
  });
  const personal = useQuery({
    queryKey: ['search', 'personal', term],
    queryFn: () => api.items('personal', false, term),
    enabled: term.length > 0,
  });

  const results = useMemo(() => [...(work.data ?? []), ...(personal.data ?? [])].slice(0, 20), [work.data, personal.data]);

  useEffect(() => setActiveIndex(0), [term]);

  function onInputKeyDown(event: KeyboardEvent) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const item = results[activeIndex];
      if (item) onOpenItem(item);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-panel search-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="search-dialog-title"
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="panel-header">
          <div>
            <p className="eyebrow">Search</p>
            <h2 id="search-dialog-title">全局搜索</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭">
            <X size={16} />
          </button>
        </header>
        <div className="search-input-row">
          <Search size={16} />
          <input
            data-autofocus
            placeholder="搜索标题或备注（工作 + 个人）"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onInputKeyDown}
          />
        </div>
        {term.length > 0 && (work.isLoading || personal.isLoading) && <p className="hint">搜索中…</p>}
        {term.length > 0 && (work.isError || personal.isError) && <p className="error-line">搜索失败，请重试</p>}
        {term.length > 0 && results.length === 0 && !work.isLoading && !personal.isLoading && (
          <p className="empty">没有匹配「{term}」的事项</p>
        )}
        <ul className="search-results">
          {results.map((item, index) => {
            const badge = scheduleBadge(item);
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={index === activeIndex ? 'search-result active' : 'search-result'}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => onOpenItem(item)}
                >
                  <span className="chip">{scopeLabel(item.scope)}</span>
                  <strong>{item.title}</strong>
                  <small>{badge.label}</small>
                </button>
              </li>
            );
          })}
        </ul>
        <p className="hint">↑↓ 选择 · Enter 打开 · Esc 关闭</p>
      </div>
    </div>
  );
}
