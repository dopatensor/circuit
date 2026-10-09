import { useState } from "react";
import { Chip } from "./ds";

export type ChipOption = { id: string; name: string; group?: string };

/** Tap-to-select chips from a fixed list. The chosen and suggested ones show first;
 *  "Show all" opens the whole list, grouped. */
export function ChipPicker({
  label,
  hint,
  options,
  selected,
  suggested = [],
  max,
  onToggle,
  startOpen = false,
}: {
  label: string;
  hint: string;
  options: ChipOption[];
  selected: string[];
  suggested?: string[];
  max: number;
  onToggle: (id: string) => void;
  startOpen?: boolean;
}) {
  const [open, setOpen] = useState(startOpen);
  const chosen = new Set(selected);
  const full = selected.length >= max;
  const front = new Set([...selected, ...suggested]);
  const shown = open ? options : options.filter((o) => front.has(o.id));
  const groups = open
    ? [...new Set(options.map((o) => o.group ?? ""))].map((g) => ({
        name: g,
        items: shown.filter((o) => (o.group ?? "") === g),
      }))
    : [{ name: "", items: shown }];
  const headingId = `chips-${label.replace(/\W+/g, "-").toLowerCase()}`;

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={headingId} className="text-base font-semibold">
          {label}
        </h2>
        <span className="text-sm text-muted">
          {selected.length} of {max}
        </span>
      </div>
      <p className="text-sm text-muted">{full ? `That's the most you can pick (${max}).` : hint}</p>
      {groups.map((g) =>
        g.items.length === 0 ? null : (
          <div key={g.name} className="flex flex-col gap-2">
            {g.name && <p className="text-sm text-muted capitalize">{g.name.replace(/_/g, " ")}</p>}
            <div className="flex flex-wrap gap-2">
              {g.items.map((o) => {
                const on = chosen.has(o.id);
                return (
                  <Chip key={o.id} selected={on} disabled={!on && full} onToggle={() => onToggle(o.id)}>
                    {o.name}
                  </Chip>
                );
              })}
            </div>
          </div>
        ),
      )}
      {shown.length === 0 && <p className="text-sm text-muted">Nothing picked yet.</p>}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="min-h-11 cursor-pointer self-start text-sm font-semibold text-fg2 underline-offset-2 hover:text-fg hover:underline"
      >
        {open ? "Show fewer" : `Show all ${options.length}`}
      </button>
    </section>
  );
}
