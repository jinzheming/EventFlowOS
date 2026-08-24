import { useEffect, useRef, useState } from 'react';
import { Item } from '../api/client';

type ListKeyboardHandlers = {
  onOpen: (item: Item) => void;
  onToggle: (item: Item) => void;
};

/**
 * j/k move, Enter/e open, x toggle done on the currently focused row.
 * Ignores keystrokes while typing in form fields or with modifier keys.
 */
export function useListKeyboard(items: Item[], handlers: ListKeyboardHandlers, enabled: boolean) {
  const [focusIndex, setFocusIndex] = useState(-1);
  const itemsRef = useRef(items);
  itemsRef.current = items;
  const focusRef = useRef(focusIndex);
  focusRef.current = focusIndex;
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!enabled) return;
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if (target?.isContentEditable) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const list = itemsRef.current;
      if (event.key === 'j') {
        event.preventDefault();
        setFocusIndex(Math.min(focusRef.current + 1, list.length - 1));
      } else if (event.key === 'k') {
        event.preventDefault();
        setFocusIndex(Math.max(focusRef.current - 1, 0));
      } else if ((event.key === 'Enter' || event.key === 'e') && focusRef.current >= 0) {
        const item = list[focusRef.current];
        if (item) {
          event.preventDefault();
          handlersRef.current.onOpen(item);
        }
      } else if (event.key === 'x' && focusRef.current >= 0) {
        const item = list[focusRef.current];
        if (item) {
          event.preventDefault();
          handlersRef.current.onToggle(item);
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [enabled]);

  return { focusIndex, setFocusIndex };
}
