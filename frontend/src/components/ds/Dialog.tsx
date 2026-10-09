import { useDrag } from "@use-gesture/react";
import { AnimatePresence, animate, m, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { type ReactNode, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Icon } from "./Icon";

const PHONE = "(max-width: 767px)";
function subscribe(cb: () => void) {
  const mq = window.matchMedia(PHONE);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}
/** True below 768px (phones). */
export function useIsPhone() {
  return useSyncExternalStore(subscribe, () => window.matchMedia(PHONE).matches, () => false);
}

const SPRING = { type: "spring", stiffness: 420, damping: 38, mass: 0.9 } as const;
const FADE = { duration: 0.12 } as const;

/**
 * The base for sheets and modals, built on <dialog> so focus trapping, Escape and the
 * inert page behind work without extra code. The dialog stays open until the closing
 * animation finishes.
 *  - "sheet": a bottom sheet on phones (drag the top down to dismiss), a centred panel
 *    from 768px.
 *  - "modal": a centred panel at every width.
 */
function DialogBase({
  open,
  onClose,
  title,
  children,
  variant,
  footer,
  hideTitle = false,
  width = "max-w-xl",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  variant: "sheet" | "modal";
  footer?: ReactNode;
  hideTitle?: boolean;
  width?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [mounted, setMounted] = useState(open);
  const phone = useIsPhone();
  const reduced = useReducedMotion();
  const asSheet = variant === "sheet" && phone;

  // Drag-to-dismiss (phones): the panel follows the finger downwards only.
  const y = useMotionValue(0);
  const scrimOpacity = useTransform(y, [0, 400], [1, 0.2]);
  const bind = useDrag(
    ({ last, movement: [, my], velocity: [, vy], direction: [, dy], cancel, event }) => {
      if (!asSheet) return cancel();
      if (event.type === "pointerdown" && (event.target as HTMLElement).closest("button,a,input,textarea,select")) {
        return cancel();
      }
      if (last) {
        if (my > 120 || (vy > 0.5 && dy > 0)) onClose();
        else animate(y, 0, SPRING);
      } else {
        y.set(Math.max(0, my));
      }
    },
    { axis: "y", filterTaps: true },
  );

  useEffect(() => {
    if (open) {
      setMounted(true);
      y.set(0);
    }
  }, [open, y]);
  useEffect(() => {
    const d = ref.current;
    if (mounted && d && !d.open) d.showModal();
  }, [mounted]);

  if (!mounted) return null;

  const panelMotion = reduced
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: FADE }
    : asSheet
      ? { initial: { y: "100%" }, animate: { y: 0 }, exit: { y: "100%" }, transition: SPRING }
      : {
          initial: { opacity: 0, scale: 0.97 },
          animate: { opacity: 1, scale: 1 },
          exit: { opacity: 0, scale: 0.98 },
          transition: { duration: 0.16, ease: [0.2, 0.8, 0.2, 1] as const },
        };

  return (
    <dialog
      ref={ref}
      aria-label={title}
      // Escape: let our exit animation run instead of closing at once.
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      className="fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none overflow-hidden bg-transparent p-0 text-fg backdrop:bg-transparent"
    >
      <AnimatePresence
        onExitComplete={() => {
          ref.current?.close();
          setMounted(false);
        }}
      >
        {open && (
          <div key="layer" className={`flex h-full w-full ${asSheet ? "items-end" : "items-center justify-center p-4"}`}>
            <m.div
              aria-hidden="true"
              className="absolute inset-0 bg-[var(--scrim)]"
              style={asSheet ? { opacity: scrimOpacity } : undefined}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              onClick={onClose}
            />
            <m.div
              {...panelMotion}
              style={asSheet ? { y } : undefined}
              className={`relative flex max-h-[88dvh] w-full flex-col overflow-hidden border-line2 bg-panel ${
                asSheet ? "rounded-t-2xl border-t shadow-sheet" : `${width} rounded-xl border`
              }`}
            >
              <div {...(asSheet ? bind() : {})} className={asSheet ? "touch-none" : ""}>
                {asSheet && <div aria-hidden="true" className="mx-auto mt-2 h-1 w-9 rounded-full bg-line2" />}
                <div className={`flex items-center justify-between gap-4 px-5 ${asSheet ? "pt-3 pb-3" : "pt-4 pb-3"}`}>
                  {/* Focus lands on the title when the dialog opens, not on Close. */}
                  <h2
                    tabIndex={-1}
                    autoFocus
                    className={`text-lg font-semibold outline-none ${hideTitle ? "sr-only" : ""}`}
                  >
                    {title}
                  </h2>
                  <button
                    type="button"
                    onClick={onClose}
                    aria-label="Close"
                    className="-mr-2 inline-flex size-11 cursor-pointer items-center justify-center rounded-lg text-fg2 hover:bg-raised hover:text-fg"
                  >
                    <Icon name="x" size={20} />
                  </button>
                </div>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5">{children}</div>
              {footer && <div className="pb-safe border-t border-line px-5 py-3">{footer}</div>}
              {asSheet && !footer && <div className="pb-safe" />}
            </m.div>
          </div>
        )}
      </AnimatePresence>
    </dialog>
  );
}

type DialogProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  hideTitle?: boolean;
};

/** Bottom sheet on phones, centred panel on laptops. */
export function BottomSheet(props: DialogProps) {
  return <DialogBase variant="sheet" {...props} />;
}

/** Centred panel at every width (confirmations, search). */
export function Modal({ width, ...props }: DialogProps & { width?: string }) {
  return <DialogBase variant="modal" width={width} {...props} />;
}
