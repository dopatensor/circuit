// Inline SVG icons on a 24px grid, 1.6px stroke. Drawn by hand so we don't need an
// icon library. Icons are decorative (aria-hidden): the text next to them says what
// they mean.

import { useId } from "react";

const PATHS = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  circuit:
    "M12 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM5 16a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM19 16a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM10.6 6.5 6.2 16.3M13.4 6.5l4.4 9.8M7 18h10",
  inbox: "M4 5h16v11H9l-5 4z",
  bell: "M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0",
  user: "M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21a8 8 0 0 1 16 0",
  briefcase: "M3 7h18v13H3zM9 7V5h6v2M3 12h18",
  plus: "M12 5v14M5 12h14",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  hand: "M7 11V6a1.5 1.5 0 0 1 3 0v4M10 10V4.5a1.5 1.5 0 0 1 3 0V10M13 10V5.5a1.5 1.5 0 0 1 3 0V12M16 9.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7h-.5a6 6 0 0 1-4.6-2.2L4 15.5a1.6 1.6 0 0 1 2.4-2.1L7 14",
  check: "M5 12.5 9.5 17 19 7.5",
  x: "M6 6l12 12M18 6 6 18",
  chevronRight: "M9 6l6 6-6 6",
  chevronDown: "M6 9l6 6 6-6",
  arrowLeft: "M19 12H5M11 6l-6 6 6 6",
  pin: "M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21zM12 7a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
  school: "M3 9l9-5 9 5-9 5zM7 11v5c3 2 7 2 10 0v-5",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  github:
    "M9 19c-4 1.5-4-2-6-2.5m12 5v-3.5a3 3 0 0 0-.9-2.4c3-.3 6-1.5 6-6.6a5 5 0 0 0-1.4-3.6 4.7 4.7 0 0 0-.1-3.6s-1.1-.3-3.7 1.4a12.8 12.8 0 0 0-6.6 0C5.7 1.6 4.6 1.9 4.6 1.9a4.7 4.7 0 0 0-.1 3.6A5 5 0 0 0 3 9.1c0 5.1 3 6.3 6 6.6a3 3 0 0 0-.9 2.3V22",
  doc: "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
  share: "M12 3v12M7 8l5-5 5 5M5 14v6h14v-6",
  more: "M5 11.5h.01M12 11.5h.01M19 11.5h.01",
  bridge: "M5 9.8a2.2 2.2 0 1 0 0 4.4 2.2 2.2 0 0 0 0-4.4zM19 9.8a2.2 2.2 0 1 0 0 4.4 2.2 2.2 0 0 0 0-4.4zM7.2 12h9.6",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
  lock: "M5 11h14v10H5zM8 11V8a4 4 0 0 1 8 0v3",
  star: "M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z",
  eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  map: "M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14",
  people:
    "M9 4.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM2.5 20a6.5 6.5 0 0 1 13 0M17 6.5a2.5 2.5 0 1 0 0 5M17 14a5 5 0 0 1 4.5 5",
  building: "M4 21V5l8-2v18M12 8h8v13M8 8h.01M8 12h.01M8 16h.01M16 12h.01M16 16h.01M2 21h20",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5M12 8h.01",
} as const;

export type IconName = keyof typeof PATHS;
export const ICON_NAMES = Object.keys(PATHS) as IconName[];

export function Icon({
  name,
  size = 20,
  className = "",
  filled = false,
}: {
  name: IconName;
  size?: number;
  className?: string;
  filled?: boolean;
}) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={name === "more" ? 3 : 1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

/** The Circuit mark: a "C" traced like a circuit board, with a lime and a blue
 *  terminal and an orange chip. Drawn on the logo file's 1600-unit grid; the same
 *  drawing as scripts/make-icons.mjs. The gaps around the terminals are cut out with a
 *  mask, so whatever is behind the logo shows through. */
export function Logo({ size = 22 }: { size?: number }) {
  const mask = `logo-cut-${useId()}`;
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="12 100 1400 1400">
      <mask id={mask}>
        <rect x="0" y="0" width="1600" height="1600" fill="white" />
        <circle cx="1200" cy="425" r="150" fill="black" />
        <circle cx="1200" cy="1175" r="150" fill="black" />
      </mask>
      <path d={LOGO_C} fill="var(--fg)" mask={`url(#${mask})`} />
      <rect x="500" y="900" width="200" height="200" fill="#FF4F00" />
      <circle cx="1200" cy="425" r="88" fill="none" stroke="#CCFF00" strokeWidth="49" />
      <circle cx="1200" cy="425" r="25" fill="#CCFF00" />
      <circle cx="1200" cy="1175" r="88" fill="none" stroke="#3B82F6" strokeWidth="49" />
      <circle cx="1200" cy="1175" r="25" fill="#3B82F6" />
    </svg>
  );
}

/** The C and the trace that runs from its top arm down to the chip. */
const LOGO_C =
  "M112 388L388 112H1012L1200 300V470H842L644 668V862H556V632L806 382H1032L938 288H462L288 462V1138" +
  "L462 1312H938L1125 1125L1250 1250L1012 1488H388L112 1212Z";
