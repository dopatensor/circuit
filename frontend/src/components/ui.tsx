// The names screens used before the redesign, now built from the design system
// (./ds). New code should import from "./ds" directly.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Avatar as DsAvatar, Badge, Button, ErrorBlock, SkeletonBlock } from "./ds";

export { BridgeBadge, UNLOCKS, VerificationBadge } from "./ds";

/** The page title. */
export function Title({ children }: { children: ReactNode }) {
  return <h1 className="text-2xl font-semibold tracking-[-0.015em]">{children}</h1>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

/** A small uppercase label above a section. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-xs font-semibold tracking-[0.06em] text-muted uppercase">{children}</p>;
}

/** A bordered panel: the main way screens are structured. */
export function Card({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "li" | "article";
}) {
  return <Tag className={`rounded-xl border border-line bg-panel p-5 ${className}`}>{children}</Tag>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;

/** The one main action on a screen. */
export function PrimaryButton(props: ButtonProps) {
  return <Button variant="primary" {...props} />;
}

export function SecondaryButton(props: ButtonProps) {
  return <Button variant="secondary" {...props} />;
}

const AVATAR = { sm: 32, md: 40, lg: 56 } as const;
/** Initials in a circle. */
export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  return <DsAvatar name={name} size={AVATAR[size]} />;
}

/** A status label. "green" (good news) is an outlined neutral badge and "blue" (in
 *  progress) the lime tint; colour is never the only signal, the words say it. */
export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "green" | "blue" | "neutral" }) {
  return <Badge tone={tone === "green" ? "outline" : tone === "blue" ? "accent" : "neutral"}>{children}</Badge>;
}

/** Loading: grey blocks shaped like the content (no spinners). */
export function Skeleton({ lines = 3, className = "h-16" }: { lines?: number; className?: string }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="flex flex-col gap-3">
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonBlock key={i} className={`w-full rounded-xl ${className}`} />
      ))}
    </div>
  );
}

/** Nothing to show yet, in one plain sentence. */
export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-line2 px-5 py-8 text-fg2">{children}</div>;
}

/** Something failed: one plain sentence and a way to try again. */
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return <ErrorBlock error={error} retry={retry} />;
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
    <div className="flex flex-col gap-1 rounded-xl border border-line bg-panel p-4">
      <span className="num text-display">{value}</span>
      <span className="text-sm text-muted">{label}</span>
    </div>
  );
}
