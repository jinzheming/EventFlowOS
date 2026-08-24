import { RefObject, useEffect } from 'react';

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Dialog 无障碍：打开时记录当前焦点并聚焦容器内首个可交互元素
 * （优先 [data-autofocus]），Tab 在容器内循环，Escape 关闭（capture 阶段 +
 * stopPropagation，避免触发页面级快捷键），卸载后焦点还给触发元素。
 */
export function useDialogA11y(ref: RefObject<HTMLElement | null>, onClose: () => void) {
  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    const previous = document.activeElement as HTMLElement | null;
    const target = (container.querySelector('[data-autofocus]') ?? container.querySelector(FOCUSABLE)) as HTMLElement | null;
    target?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusables = Array.from(container!.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null);
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      previous?.focus?.();
    };
  }, [ref, onClose]);
}
