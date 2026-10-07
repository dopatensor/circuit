// The building blocks every screen uses. Neon blue only for the main action; neon
// green for the Bridge badge and good news. Everything else is black, white and grey.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ApiError } from "../api/client";

export function Title({ children }: { children: ReactNode }) {
  return <h1 className="text-xl font-semibold tracking-tight">{children}</h1>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

/** A small uppercase label above a section. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-sm font-medium tracking-wide text-muted uppercase">{children}</p>;
}

/** A soft rounded panel: the main way screens are structured. */
export function Card({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "li" | "article";
}) {
  return (
    <Tag className={`rounded-2xl border border-line bg-surface p-5 ${className}`}>{children}</Tag>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;
const base =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-base " +
  "font-semibold transition disabled:opacity-40 cursor-pointer disabled:cursor-default";

/** The one main action on a screen: neon blue, with a soft glow. */
export function PrimaryButton({ className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`${base} bg-blue text-black shadow-glow-blue hover:brightness-110 active:brightness-95 ${className}`}
      {...props}
    />
  );
}

export function SecondaryButton({ className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`${base} border border-line bg-raised text-fg hover:border-muted ${className}`}
      {...props}
    />
  );
}

/** Initials in a circle: people get a recognisable mark without photos. */
export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  const initials = name
    .replace(/^(Dr|Mr|Ms|Mrs|Prof)\.?\s+/i, "")
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  const sizes = { sm: "size-9 text-sm", md: "size-11 text-base", lg: "size-16 text-xl" };
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center rounded-full border border-blue/50 bg-raised font-semibold text-fg ${sizes[size]}`}
    >
      {initials}
    </span>
  );
}

/** A status label with a tinted background: green for good news, blue for in
 *  progress, grey for everything else. */
export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "green" | "blue" | "neutral";
}) {
  const tones = {
    green: "bg-green/10 text-green border-green/30",
    blue: "bg-blue/10 text-blue border-blue/30",
    neutral: "bg-raised text-muted border-line",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-sm font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

/** The Bridge match badge (cross-sector match): neon green with a glow. */
export function BridgeBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-green/60 bg-green/10 px-2.5 py-0.5 text-sm font-semibold text-green shadow-glow-green">
      <span aria-hidden="true" className="size-1.5 rounded-full bg-green" />
      Bridge match
    </span>
  );
}

const LEVELS = ["Not verified", "Email verified", "Work verified", "Role verified"];
export const UNLOCKS = [
  "Verify your email to start browsing.",
  "You can browse startups and people.",
  "You can see your matches.",
  "You can see matches and ask for warm intros.",
];

/** Verification level (F7) in words. Level 3 is shown in green. */
export function VerificationBadge({ level }: { level: number }) {
  const i = Math.max(0, Math.min(3, level));
  return (
    <span data-testid="verification-badge" title={UNLOCKS[i]}>
      <Pill tone={i === 3 ? "green" : i === 2 ? "blue" : "neutral"}>{LEVELS[i]}</Pill>
    </span>
  );
}

/** Loading: grey blocks shaped like the content (no spinners). */
export function Skeleton({ lines = 3, className = "h-16" }: { lines?: number; className?: string }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="flex flex-col gap-3">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className={`animate-pulse rounded-2xl bg-surface ${className}`} />
      ))}
    </div>
  );
}

/** Nothing to show yet, in one plain sentence. */
export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-line px-6 py-12 text-center text-muted">
      {children}
    </div>
  );
}

/** Something failed: one plain sentence and a way to try again. */
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message =
    error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-4 rounded-2xl border border-line bg-surface px-6 py-10 text-center"
    >
      <p>{message}</p>
      {retry && <SecondaryButton onClick={retry}>Try again</SecondaryButton>}
    </div>
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

/** A big number with a label, for stat tiles. */
export function Stat({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-line bg-surface p-4">
      <span className="text-display font-semibold tracking-tight">{value}</span>
      <span className="text-sm text-muted">{label}</span>
    </div>
  );
}
