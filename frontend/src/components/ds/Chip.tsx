import type { ReactNode } from "react";
import { Icon } from "./Icon";

/** A tap-to-select chip (aria-pressed). Selected chips get a dark outline and a tick, so
 *  the state never depends on colour alone. */
export function Chip({
  selected = false,
  onToggle,
  children,
  detail,
  disabled,
}: {
  selected?: boolean;
  onToggle?: () => void;
  children: ReactNode;
  detail?: ReactNode;
  disabled?: boolean;
}) {
  const cls = `inline-flex min-h-11 md:min-h-9 items-center gap-1.5 rounded-md px-3 text-sm transition-[transform,background-color,box-shadow] duration-150 ${
    selected ? "bg-panel text-fg ring-[1.5px] ring-fg ring-inset" : "bg-raised text-fg"
  }`;
  if (!onToggle)
    return (
      <span className={cls}>
        {children}
        {detail && <span className="text-xs text-muted">{detail}</span>}
      </span>
    );
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      disabled={disabled}
      className={`${cls} cursor-pointer active:scale-[0.96] disabled:cursor-default disabled:opacity-40`}
    >
      {selected && <Icon name="check" size={14} />}
      {children}
      {detail && <span className="text-xs text-muted">{detail}</span>}
    </button>
  );
}

/** A removable chip (for filters that are on). */
export function RemovableChip({ children, onRemove }: { children: ReactNode; onRemove: () => void }) {
  return (
    <span className="inline-flex min-h-9 items-center gap-1 rounded-md bg-raised pr-1 pl-3 text-sm">
      {children}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${typeof children === "string" ? children : "filter"}`}
        className="inline-flex size-7 cursor-pointer items-center justify-center rounded text-muted hover:bg-line hover:text-fg"
      >
        <Icon name="x" size={14} />
      </button>
    </span>
  );
}
