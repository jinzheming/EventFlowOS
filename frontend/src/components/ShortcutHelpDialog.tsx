import { X } from 'lucide-react';
import { useRef } from 'react';
import { useDialogA11y } from '../hooks/useDialogA11y';

const SHORTCUTS: Array<{ keys: string; description: string }> = [
  { keys: '⌘/Ctrl + K', description: '打开快速添加' },
  { keys: '⌘/Ctrl + P', description: '打开全局搜索' },
  { keys: '?', description: '打开 / 关闭本帮助' },
  { keys: 'j / k', description: '列表中向下 / 向上移动焦点' },
  { keys: 'Enter 或 e', description: '打开焦点事项详情' },
  { keys: 'x', description: '完成 / 取消完成焦点事项' },
  { keys: 'Esc', description: '关闭弹窗或抽屉' },
];

export function ShortcutHelpDialog({ onClose }: { onClose: () => void }) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogA11y(panelRef, onClose);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-panel shortcut-help-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcut-help-title"
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="panel-header">
          <div>
            <p className="eyebrow">Shortcuts</p>
            <h2 id="shortcut-help-title">快捷键</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭" data-autofocus>
            <X size={16} />
          </button>
        </header>
        <ul className="shortcut-list">
          {SHORTCUTS.map((shortcut) => (
            <li key={shortcut.keys}>
              <kbd>{shortcut.keys}</kbd>
              <span>{shortcut.description}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
