import { ReactNode, createContext, useCallback, useContext, useRef, useState } from 'react';

type UndoEntry = {
  id: number;
  label: string;
  undo: () => void;
};

type UndoContextValue = {
  pushUndo: (label: string, undo: () => void) => void;
};

const UndoContext = createContext<UndoContextValue>({ pushUndo: () => undefined });

export function useUndo() {
  return useContext(UndoContext);
}

// Keep in sync with the undo-toast-countdown animation duration in app.css.
const UNDO_WINDOW_MS = 10000;

export function UndoProvider({ children }: { children: ReactNode }) {
  const [entry, setEntry] = useState<UndoEntry | null>(null);
  const timerRef = useRef<number | null>(null);
  const nextIdRef = useRef(1);

  const clear = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setEntry(null);
  }, []);

  const pushUndo = useCallback(
    (label: string, undo: () => void) => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      const id = nextIdRef.current++;
      setEntry({ id, label, undo });
      timerRef.current = window.setTimeout(() => {
        setEntry((current) => (current?.id === id ? null : current));
        timerRef.current = null;
      }, UNDO_WINDOW_MS);
    },
    [],
  );

  function runUndo() {
    const current = entry;
    clear();
    current?.undo();
  }

  return (
    <UndoContext.Provider value={{ pushUndo }}>
      {children}
      {entry && (
        <div className="undo-toast" role="status">
          <span>{entry.label}</span>
          <button className="ghost sm" type="button" onClick={runUndo}>
            撤销
          </button>
          <button className="ghost sm" type="button" onClick={clear}>
            关闭
          </button>
          <div className="undo-toast-progress" key={entry.id} />
        </div>
      )}
    </UndoContext.Provider>
  );
}
