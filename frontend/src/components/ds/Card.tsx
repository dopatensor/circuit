import type { ReactNode } from "react";
import { Link } from "react-router";
import { Icon } from "./Icon";

/** A bordered panel. No shadows: the 1px border does the work. */
export function Card({
  children,
  className = "",
  as: Tag = "section",
  padded = true,
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "li" | "article";
  padded?: boolean;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <Tag className={`rounded-xl border border-line bg-panel ${padded ? "p-5" : ""} ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

/** A section of a page: heading on the left, an optional "See all" link on the right. */
export function Section({
  title,
  action,
  children,
  className = "",
}: {
  title: string;
  action?: { label: string; to: string };
  children: ReactNode;
  className?: string;
}) {
  const id = `section-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <section aria-labelledby={id} className={`flex flex-col gap-3 ${className}`}>
      <div className="flex items-baseline justify-between gap-4">
        <h2 id={id} className="text-lg font-semibold">
          {title}
        </h2>
        {action && (
          <Link to={action.to} className="text-sm font-semibold text-fg2 hover:text-fg">
            {action.label}
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

/** Rows inside one bordered card (a list, not a grid of cards). */
export function List({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <ul aria-label={label} className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-panel">
      {children}
    </ul>
  );
}

/** One row: leading avatar, title, meta, an optional "why" line and a trailing value. */
export function ListRow({
  leading,
  title,
  meta,
  why,
  trailing,
  to,
  onClick,
}: {
  leading?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  why?: ReactNode;
  trailing?: ReactNode;
  to?: string;
  onClick?: () => void;
}) {
  const body = (
    <>
      {leading}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="font-semibold">{title}</span>
        {meta && <span className="text-sm text-muted">{meta}</span>}
        {why && <span className="mt-1.5 text-sm text-fg2">{why}</span>}
      </span>
      {trailing}
      {(to || onClick) && !trailing && <Icon name="chevronRight" size={16} className="self-center text-muted" />}
    </>
  );
  const cls = "flex items-start gap-3 px-4 py-3.5";
  return (
    <li>
      {to ? (
        <Link to={to} className={`${cls} transition-colors hover:bg-raised/60`}>
          {body}
        </Link>
      ) : onClick ? (
        <button type="button" onClick={onClick} className={`${cls} w-full cursor-pointer text-left hover:bg-raised/60`}>
          {body}
        </button>
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
  );
}

/** A match score or other standalone number, in mono. */
export function Score({ value, label = "match" }: { value: number; label?: string }) {
  return (
    <span className="flex shrink-0 flex-col items-end">
      <span className="num text-[15px] leading-5">{value}%</span>
      <span className="text-xs text-muted">{label}</span>
    </span>
  );
}
