// The few building blocks every screen uses. One accent colour, only for the main
// action (PrimaryButton) and the Bridge badge.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ApiError } from "../api/client";

export function Title({ children }: { children: ReactNode }) {
  return <h1 className="text-xl font-semibold tracking-tight">{children}</h1>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;
const base =
  "min-h-11 rounded-full px-5 text-base font-medium transition-opacity disabled:opacity-40 " +
  "active:opacity-80 cursor-pointer";

/** The one main action on a screen. */
export function PrimaryButton({ className = "", ...props }: ButtonProps) {
  return <button className={`${base} bg-accent text-accent-fg ${className}`} {...props} />;
}

export function SecondaryButton({ className = "", ...props }: ButtonProps) {
  return <button className={`${base} border border-line ${className}`} {...props} />;
}

/** Loading: grey blocks shaped like the content (no spinners). */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="flex flex-col gap-3">
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-14 animate-pulse rounded-xl bg-surface"
          style={{ width: `${100 - (i % 3) * 12}%` }}
        />
      ))}
    </div>
  );
}

/** Nothing to show yet, in one plain sentence. */
export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-10 text-center text-muted">{children}</p>;
}

/** Something failed: one plain sentence and a way to try again. */
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message =
    error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
  return (
    <div role="alert" className="flex flex-col items-center gap-4 py-10 text-center">
      <p>{message}</p>
      {retry && <SecondaryButton onClick={retry}>Try again</SecondaryButton>}
    </div>
  );
}

const LEVELS = ["Not verified", "Email verified", "Work verified", "Role verified"];
const UNLOCKS = [
  "Verify your email to browse.",
  "Can browse startups and people.",
  "Can see matches.",
  "Can see matches and ask for intros.",
];

/** Verification level (F7) as words, not a symbol. */
export function VerificationBadge({ level }: { level: number }) {
  const i = Math.max(0, Math.min(3, level));
  return (
    <span
      title={UNLOCKS[i]}
      data-testid="verification-badge"
      className="inline-flex items-center rounded-full border border-line px-2.5 py-0.5 text-sm"
    >
      {LEVELS[i]}
    </span>
  );
}

/** The Bridge match badge: the only other place the accent colour appears. */
export function BridgeBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-accent px-2.5 py-0.5 text-sm font-medium text-accent-fg">
      Bridge match
    </span>
  );
}

/** "Last updated 10:42" when the data may be old: offline, or served from cache. */
export function LastUpdated({ servedAt }: { servedAt: Date | null | undefined }) {
  if (!servedAt) return null;
  const old = Date.now() - servedAt.getTime() > 60_000;
  if (!old && navigator.onLine) return null;
  const time = servedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const day =
    new Date().toDateString() === servedAt.toDateString()
      ? ""
      : ` ${servedAt.toLocaleDateString([], { day: "numeric", month: "short" })}`;
  return (
    <p data-testid="last-updated" className="text-sm text-muted">
      Last updated {time}
      {day}
    </p>
  );
}
