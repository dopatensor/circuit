import { AnimatePresence, m, useReducedMotion } from "motion/react";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

type Toast = { id: number; message: string; action?: { label: string; onClick: () => void }; duration: number };
type Show = (t: { message: string; action?: Toast["action"]; duration?: number }) => void;

const ToastContext = createContext<Show>(() => {});

/** Short messages at the bottom of the screen, with an optional action such as Undo.
 *  Announced to screen readers (aria-live). One toast at a time; a new one replaces it. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const next = useRef(1);
  const show = useCallback<Show>(({ message, action, duration }) => {
    setToast({ id: next.current++, message, action, duration: duration ?? (action ? 5000 : 3000) });
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <ToastView toast={toast} onDone={() => setToast(null)} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

function ToastView({ toast, onDone }: { toast: Toast | null; onDone: () => void }) {
  const reduced = useReducedMotion();
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(onDone, toast.duration);
    return () => clearTimeout(t);
  }, [toast, onDone]);
  const motion = useMemo(
    () =>
      reduced
        ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } }
        : { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: 8 } },
    [reduced],
  );
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-[calc(5rem+env(safe-area-inset-bottom))] z-50 flex justify-center px-4 md:bottom-6"
    >
      <AnimatePresence>
        {toast && (
          <m.div
            key={toast.id}
            {...motion}
            transition={{ type: "spring", stiffness: 500, damping: 40 }}
            role="status"
            className="pointer-events-auto flex min-h-12 max-w-md items-center gap-4 rounded-lg bg-fg py-2 pr-2 pl-4 text-sm text-bg"
          >
            <span>{toast.message}</span>
            {toast.action && (
              <button
                type="button"
                onClick={() => {
                  toast.action!.onClick();
                  onDone();
                }}
                className="min-h-10 cursor-pointer rounded-md px-3 font-semibold text-bg underline-offset-2 hover:underline"
              >
                {toast.action.label}
              </button>
            )}
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
