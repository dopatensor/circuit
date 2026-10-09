import { type KeyboardEvent, useRef } from "react";
import { NavLink } from "react-router";
import { m } from "motion/react";

/** Tabs that switch content on the same page (role="tablist", arrow keys move between
 *  tabs). The underline slides to the selected tab with a shared layout animation. */
export function Tabs<K extends string>({
  tabs,
  value,
  onChange,
  label,
  id = "tabs",
}: {
  tabs: readonly (readonly [K, string])[];
  value: K;
  onChange: (key: K) => void;
  label: string;
  id?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = (i + dir + tabs.length) % tabs.length;
    refs.current[next]?.focus();
    onChange(tabs[next][0]);
  };
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 border-b border-line">
      {tabs.map(([key, text], i) => {
        const on = key === value;
        return (
          <button
            key={key}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="tab"
            id={`${id}-${key}`}
            aria-selected={on}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(key)}
            onKeyDown={(e) => onKey(e, i)}
            className={`relative min-h-11 cursor-pointer px-3 text-sm font-semibold transition-colors ${
              on ? "text-fg" : "text-muted hover:text-fg"
            }`}
          >
            {text}
            {on && <m.span layoutId={`${id}-underline`} className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-fg" />}
          </button>
        );
      })}
    </div>
  );
}

/** Tabs that are links to sub-pages (Discover: Matches, Jobs, Startups, Map). A nav
 *  landmark with aria-current, since each tab is its own URL. */
export function TabLinks({ tabs, label }: { tabs: { to: string; label: string }[]; label: string }) {
  return (
    <nav aria-label={label} className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
      <div className="flex min-w-max gap-1 border-b border-line">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={false}
            className={({ isActive }) =>
              `relative flex min-h-11 items-center px-3 text-sm font-semibold transition-colors ${
                isActive
                  ? "text-fg after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-fg"
                  : "text-muted hover:text-fg"
              }`
            }
          >
            {t.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
