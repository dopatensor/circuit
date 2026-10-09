import type { ReactNode } from "react";
import { ApiError } from "../../api/client";
import { Button } from "./Button";
import { Icon, type IconName } from "./Icon";

/** A grey block with a moving highlight (transform only). Shaped like the content. */
export function SkeletonBlock({ className = "h-4 w-full" }: { className?: string }) {
  return (
    <span aria-hidden="true" className={`relative block overflow-hidden rounded-md bg-raised ${className}`}>
      <span className="absolute inset-0 animate-shimmer bg-[linear-gradient(90deg,transparent,color-mix(in_srgb,var(--panel)_70%,transparent),transparent)]" />
    </span>
  );
}

/** Loading rows: avatar, two lines, like a list row. */
export function SkeletonRows({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div aria-busy="true" aria-label={label} role="status" className="divide-y divide-line rounded-xl border border-line bg-panel">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-3.5">
          <SkeletonBlock className="size-10 shrink-0 rounded-lg" />
          <div className="flex flex-1 flex-col gap-2 pt-1">
            <SkeletonBlock className="h-4 w-3/5" />
            <SkeletonBlock className="h-3 w-2/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Nothing here yet: what this place is for, and the one thing to do about it. */
export function EmptyState({
  icon = "info",
  title,
  children,
  action,
}: {
  icon?: IconName;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-line2 px-5 py-8">
      <Icon name={icon} size={22} className="text-muted" />
      <div>
        <p className="font-semibold">{title}</p>
        {children && <p className="mt-1 text-sm text-fg2">{children}</p>}
      </div>
      {action}
    </div>
  );
}

/** Something failed: one plain sentence and a way to try again. */
export function ErrorBlock({ error, retry }: { error: unknown; retry?: () => void }) {
  const message =
    error instanceof ApiError
      ? error.message
      : "We couldn't load this. Check your connection and try again.";
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-line bg-panel px-5 py-6">
      <p>{message}</p>
      {retry && (
        <Button size="sm" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
