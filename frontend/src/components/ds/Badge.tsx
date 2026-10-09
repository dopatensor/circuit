import { type ReactNode, useEffect, useRef, useState } from "react";
import { Icon, type IconName } from "./Icon";

/** A small label. Neutral by default; `bridge` (teal) only for cross-sector matches and
 *  circuits; `outline` for trust signals such as verification. */
export function Badge({
  children,
  tone = "neutral",
  icon,
  className = "",
}: {
  children: ReactNode;
  tone?: "neutral" | "outline" | "bridge" | "accent";
  icon?: IconName;
  className?: string;
}) {
  const tones = {
    neutral: "bg-raised text-fg2",
    outline: "text-fg ring-1 ring-line2 ring-inset",
    bridge: "bg-signal-bg text-signal",
    accent: "bg-accent-bg text-accent",
  };
  return (
    <span
      className={`inline-flex h-6 items-center gap-1 whitespace-nowrap rounded px-2 text-xs font-semibold ${tones[tone]} ${className}`}
    >
      {icon && <Icon name={icon} size={13} />}
      {children}
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

/** Verification level (F7) in words. When the level goes up while you're looking, the
 *  badge pops once (scale only; nothing with reduced motion). */
export function VerificationBadge({ level }: { level: number }) {
  const i = Math.max(0, Math.min(3, level));
  const prev = useRef(i);
  const [pop, setPop] = useState(false);
  useEffect(() => {
    if (i > prev.current) setPop(true);
    prev.current = i;
  }, [i]);
  return (
    <span
      data-testid="verification-badge"
      title={UNLOCKS[i]}
      onAnimationEnd={() => setPop(false)}
      className={`inline-flex ${pop ? "animate-[badge-pop_300ms_var(--ease-out)]" : ""}`}
    >
      <Badge tone={i >= 2 ? "outline" : "neutral"} icon={i >= 1 ? "check" : undefined}>
        {LEVELS[i]}
      </Badge>
    </span>
  );
}

/** Cross-sector match. Optional detail such as "deep tech ↔ biotech". */
export function BridgeBadge({ detail }: { detail?: string }) {
  return (
    <Badge tone="bridge" icon="bridge">
      Bridge match{detail ? ` · ${detail}` : ""}
    </Badge>
  );
}

/** Hiring status: a solid dot when hiring, a hollow one when not. */
export function HiringBadge({ hiring }: { hiring: boolean }) {
  return (
    <Badge>
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full ${hiring ? "bg-fg" : "ring-1 ring-muted ring-inset"}`}
      />
      {hiring ? "Hiring" : "Not hiring"}
    </Badge>
  );
}
