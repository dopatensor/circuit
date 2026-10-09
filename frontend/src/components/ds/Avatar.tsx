export type AvatarSize = 24 | 32 | 40 | 56 | 72;

export function initials(name: string) {
  const words = name.replace(/^(Dr|Mr|Ms|Mrs|Prof)\.?\s+/i, "").split(/\s+/).filter(Boolean);
  if (words.length === 1) {
    // One word: its capitals (LedgerLoop → LL, KoshFin → KF), else its first two letters.
    const caps = words[0].match(/[A-Z]/g) ?? [];
    return (caps.length >= 2 ? caps.slice(0, 2).join("") : words[0].slice(0, 2)).toUpperCase();
  }
  return words
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Initials instead of photos. People are circles; startups are rounded squares, so
 *  the two are never confused. Decorative: the name is always written next to it. */
export function Avatar({
  name,
  size = 40,
  kind = "person",
  className = "",
}: {
  name: string;
  size?: AvatarSize;
  kind?: "person" | "startup";
  className?: string;
}) {
  const font = size <= 24 ? "text-[10px]" : size <= 32 ? "text-xs" : size <= 40 ? "text-sm" : size <= 56 ? "text-lg" : "text-2xl";
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size }}
      className={`inline-flex shrink-0 items-center justify-center bg-raised font-semibold text-fg ring-1 ring-line ring-inset ${
        kind === "person" ? "rounded-full" : size <= 32 ? "rounded-md" : "rounded-lg"
      } ${font} ${className}`}
    >
      {initials(name)}
    </span>
  );
}
