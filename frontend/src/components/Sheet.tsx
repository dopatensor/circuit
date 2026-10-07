import { type ReactNode, useEffect, useRef } from "react";

/** A bottom sheet on phones and a centred panel on laptops, built on <dialog> so
 *  focus, Escape and the backdrop work without extra code. */
export function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-label={title}
      onClose={onClose}
      onClick={(e) => e.target === e.currentTarget && onClose()} // tap outside closes
      className="m-0 mt-auto max-h-[85dvh] w-full max-w-none rounded-t-3xl border border-line bg-surface p-0 text-fg backdrop:bg-black/70 md:m-auto md:max-w-xl md:rounded-3xl"
    >
      <div className="pb-safe flex flex-col">
        <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-line bg-surface px-5 py-4">
          <h2 className="text-xl font-semibold">{title}</h2>
          <button onClick={onClose} className="min-h-11 px-2 text-sm text-muted hover:text-fg">
            Close
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </dialog>
  );
}
