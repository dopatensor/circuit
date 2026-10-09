import { Icon } from "./Icon";

/** A path of steps joined by a line (the line motif: it connects real steps). The line
 *  between two finished steps is filled; it grows with a scale transform when a step is
 *  completed, so it never animates width. */
export function Stepper({ steps, current, label }: { steps: string[]; current: number; label: string }) {
  return (
    <ol aria-label={label} className="flex items-start">
      {steps.map((s, i) => {
        const state = i < current ? "done" : i === current ? "now" : "todo";
        return (
          <li
            key={s}
            aria-current={state === "now" ? "step" : undefined}
            className={`flex items-start ${i < steps.length - 1 ? "flex-1" : ""}`}
          >
            <span className="flex w-14 shrink-0 flex-col items-center gap-1.5 text-center">
              <span
                className={`flex size-[22px] items-center justify-center rounded-full text-[11px] font-semibold ${
                  state === "done"
                    ? "bg-fg text-bg"
                    : state === "now"
                      ? "bg-panel text-accent ring-[1.5px] ring-accent ring-offset-0 shadow-[0_0_0_3px_var(--accent-bg)]"
                      : "bg-panel text-muted ring-[1.5px] ring-line2"
                }`}
              >
                {state === "done" ? <Icon name="check" size={12} /> : i + 1}
              </span>
              <span className={`text-xs font-semibold ${state === "todo" ? "text-muted" : "text-fg"}`}>
                {s}
                <span className="sr-only">{state === "done" ? " (done)" : state === "now" ? " (next)" : ""}</span>
              </span>
            </span>
            {i < steps.length - 1 && (
              <span aria-hidden="true" className="relative mt-[10px] h-[1.5px] min-w-3 flex-1 bg-line2">
                <span
                  className={`absolute inset-0 origin-left bg-fg transition-transform duration-300 ease-out ${
                    i < current ? "scale-x-100" : "scale-x-0"
                  }`}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** A checklist with a segmented meter on top (profile strength). */
export function Checklist({
  items,
  title,
}: {
  title: string;
  items: { label: string; done: boolean; next?: boolean }[];
}) {
  const done = items.filter((i) => i.done).length;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold">{title}</span>
        <span className="text-sm text-muted">
          {done} of {items.length} done
        </span>
      </div>
      <div aria-hidden="true" className="mt-3 mb-3 flex gap-1">
        {items.map((it, i) => (
          <span key={i} className={`h-1 flex-1 rounded-full ${it.done ? "bg-fg" : "bg-line2"}`} />
        ))}
      </div>
      <ul className="flex flex-col">
        {items.map((it) => (
          <li key={it.label} className={`flex items-start gap-2 py-1.5 text-sm ${it.done ? "text-muted" : ""}`}>
            {it.done ? (
              <Icon name="check" size={16} className="mt-0.5" />
            ) : (
              <span
                aria-hidden="true"
                className={`mt-0.5 size-4 shrink-0 rounded-full ring-[1.5px] ring-inset ${it.next ? "ring-accent" : "ring-line2"}`}
              />
            )}
            <span className={`${it.done ? "line-through" : ""} ${it.next ? "font-semibold" : ""}`}>
              {it.label}
              <span className="sr-only">{it.done ? " (done)" : " (to do)"}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
