# Circuit — design system (redesign, R1–R7)

**Status: proposal, waiting for the user's OK (2026-10-08).** This replaces the Phase 8
"pure black and neon" brief. The PWA, performance and testing rules at the end carry
over from that brief and still apply.

Approved dependencies for the redesign: `motion`, `@tanstack/react-virtual`,
`@use-gesture/react`. Anything else: ask first. (Icons are hand-drawn inline SVG, so
no icon library is needed. Fonts are files we commit, not npm packages.)

## 1. What the product should feel like

A tool that students and founders open every day to find their next real opportunity.
Warm and confident, never corporate, never "AI startup". Three qualities we borrow, not
layouts:

- **Linear**: precision and restraint. Every pixel aligned to the grid, nothing extra.
- **Read.cv**: profiles that lead with work, written in the person's own voice.
- **Zerodha Kite**: fast, dense and trustworthy on a ₹10,000 phone on a 4G train.

The test for every screen: would a final-year student in Hubballi trust this with their
first job application, and would a founder in Koramangala use it between meetings?

## 2. Colour

Near-black and off-white neutrals carry the whole interface. Two colours have a job and
are never used for anything else:

- **Accent, "Kiln"** (burnt orange): primary actions only. One filled accent button per
  screen at most; the active nav item uses the accent as a 2px marker, not a fill.
- **Signal, "Circuit"** (deep teal): Bridge matches, exchange circuits and the line
  motif. If something is teal, it's a cross-sector connection or a loop. Nothing else.

Status (hiring, accepted, shortlisted) is shown with neutral text, weight and a small
solid or hollow dot, not with colour. Red exists only for errors and destructive
confirmations.

| Token | Light | Dark | Used for |
| --- | --- | --- | --- |
| `bg` | `#F6F5F1` | `#121110` | Page background |
| `surface` | `#FFFFFF` | `#1A1917` | Cards, sheets, nav |
| `sunken` | `#EEECE6` | `#0D0C0B` | Inputs, chips, cover strip, skeletons |
| `line` | `#E2DFD7` | `#2E2C28` | 1px borders and dividers |
| `line-strong` | `#CFCBC1` | `#45423D` | Hover borders, input borders |
| `fg` | `#1A1917` | `#EEECE7` | Headings and body text |
| `fg-2` | `#45423D` | `#C9C5BD` | Secondary text |
| `muted` | `#6B675F` | `#9C978E` | Meta text, captions, placeholders |
| `accent` | `#B8461B` | `#EE7D50` | Primary buttons, active nav marker, focus ring |
| `accent-ink` | `#FFFFFF` | `#1A0A03` | Text on accent |
| `accent-tint` | `#FBEBE3` | `#3A2016` | Pressed/selected state behind accent text |
| `signal` | `#0B7468` | `#4FC2B0` | Bridge badge, circuit loop, line motif |
| `signal-tint` | `#E3F1EE` | `#15302C` | Bridge badge background |
| `danger` | `#B42318` | `#F97066` | Errors only |

Contrast, checked with the WCAG formula (script in the R1 commit):
`fg` ≥ 14.8:1 everywhere; `muted` ≥ 4.77:1 on every surface (light) and ≥ 6.05:1 (dark);
`accent` text ≥ 4.52:1, white on accent 5.34:1, dark ink on dark accent 7.06:1;
`signal` ≥ 4.79:1 (light) and ≥ 8.09:1 (dark), and 4.87:1 on its own tint. All AA.

Light and dark follow the system setting, with a Light / Dark / System choice on Me.

## 3. Typography

- **Text: Instrument Sans**, 400 and 600 only. A slightly condensed grotesque with warm,
  open shapes: confident without looking like every other SaaS app. Self-hosted WOFF2,
  subset to Latin plus `₹ – — ’ “ ” · →` (about 18 KB per weight), `font-display: swap`,
  the 400 weight preloaded.
- **Numbers: IBM Plex Mono 500**, one weight, subset to digits and `% ₹ , . : + − km`
  (about 4 KB). Used only for numbers that stand on their own: match scores, stat
  tiles, counts in badges, stipends in a job's meta line. Never for words, and never
  for a number inside a sentence ("Used by 40 shops" stays in the text font; mono
  digits mid-sentence looked broken in the mockups).
- Left-aligned everywhere. Nothing is centred except a lone number inside a stat tile
  and the empty-state illustration line.

Type scale (px, line height). Six steps, nothing in between:

| Token | Size / line | Weight | Use |
| --- | --- | --- | --- |
| `text-xs` | 12 / 16 | 400, 600 caps +0.04em | Meta, badge labels, section labels |
| `text-sm` | 14 / 20 | 400, 600 | Secondary text; body text on desktop lists |
| `text-base` | 16 / 24 | 400, 600 | Body on mobile, card titles |
| `text-lg` | 20 / 28 | 600 | Screen titles on mobile, profile name |
| `text-xl` | 24 / 32 | 600 | Screen titles on desktop |
| `text-2xl` | 32 / 40 | 600 | Big numbers (mono), profile name on desktop |

Headings use `letter-spacing: -0.01em` at 20px and up. Body text max 68 characters per
line.

## 4. Spacing, radius, borders

- **8px grid.** Tokens: 4 (half step, only inside components), 8, 12, 16, 24, 32, 48, 64.
  Mobile screen gutter 16; desktop column gutter 24; space between cards 12 on mobile,
  8 in dense desktop lists.
- **Radius is ranked, not uniform** (no rounded-everything):
  cards and sheets 12; buttons and inputs 8; chips 6; badges 4; people avatars are
  circles; startup avatars are 8px-rounded squares (so people and companies never get
  confused); the bottom sheet's top corners 16.
- **Borders over shadows.** Cards are `surface` + 1px `line`. The only shadows: sheets
  and modals (`0 8px 32px rgb(0 0 0 / .12)` light, none in dark, where a `line-strong`
  border is used instead) and the floating centre action button (a 1px ring).
- Tap targets ≥ 44px on mobile; desktop rows may be 36px with a 44px hit area.

## 5. Layout and navigation

- **Mobile (<768px)**: top bar (title left, search and notifications right), content,
  bottom tab bar `Home · Discover · [action] · Circuits · Inbox`, with **Me** reached
  from the avatar in the top bar. Five slots: the centre is the role's main action
  (student: "Find jobs"; founder: "Post" → need or job; mentor/investor: "Offer help";
  partner admin: "Dashboard"). Unread counts as a small mono number in a neutral pill.
  _Change from the brief, to confirm:_ five tabs plus a centre button is six slots, and
  with five tabs the button can't sit in the middle (two tabs on one side, three on the
  other). I propose Home · Discover · [action] · Circuits · Inbox, with Me on your
  avatar in the top bar (where people look for it anyway). Alternative: keep Me as a
  tab and move Inbox to the top bar next to notifications.
- **Desktop (≥1200px)**: three columns. Left sidebar 232px (logo, nav with labels,
  the main action as a button, persona switcher in demo mode, you at the bottom),
  centre content max 680px, right rail 304px (profile strength, suggested connections,
  nearby jobs). Map and dashboard may span centre + rail.
- **Tablet (768–1199px)**: sidebar collapses to a 72px icon rail with labels on hover
  and focus; right rail hidden; its modules appear at the top of Home.
- **Global search**: Ctrl/⌘K on desktop opens a command-style modal; the search icon on
  mobile opens a full-screen sheet. Results grouped: People, Startups, Jobs, Skills.

## 6. Components (built first, shown on `/design`, dev only)

Avatar (initials fallback, deterministic neutral tint from the name, sizes 24/32/40/
56/88), Card, Badge (`L1/L2/L3` verification, `Bridge`, `Hiring`), Button (primary,
secondary, ghost, danger; sizes 36/44), Chip (selectable, removable), BottomSheet,
Modal, Tabs, Toast (with Undo), Skeleton (shimmer), EmptyState, plus Icon (inline SVG,
1.5px stroke, 20px grid), Meter (profile strength), Line (the motif).

Badge rules:
- **Verification**: a small square-ish badge with a check mark and the level:
  `✓ Email` (L1), `✓ Work` (L2), `✓ Role verified` (L3). Neutral (`fg` on `sunken`);
  L3 gets a 1px `fg` border. Never colourful: trust comes from restraint.
- **Bridge**: `signal` on `signal-tint` with a tiny two-node line glyph, label
  "Bridge · fintech ↔ biotech" when there's room, "Bridge" when there isn't.
- **Hiring**: neutral with a solid `fg` dot; "Not hiring" is a hollow dot.

## 7. The line motif ("circuits")

A thin **1px line in `signal`** connecting things that are actually related. Used in
exactly these places and nowhere else:

1. **Circuit loop**: the three avatars joined by a drawn loop (the signature moment).
2. **Warm-intro path**: You — mutual — them, avatars joined by a line with the mutual's
   name under it.
3. **Match reason**: on a match card, a short line from the score to the reason text
   ("why you're matched"), so the reason reads as the explanation of the number.
4. **Bridge badge glyph** (two dots joined by a line).
5. **Profile strength meter**: segments joined by the line as steps are completed.

Never as a background pattern, a divider or decoration. If a line doesn't connect two
real things, it's not there.

The profile **cover strip** is a plain `sunken` band (72px mobile, 112px desktop). No
pattern: an early mockup drew circuit lines on it and that broke the rule above.

## 8. Motion

Purposeful, fast, never decorative. Built with `motion`.

- **Durations**: 150ms (press, toggle), 200ms (fade, small moves), 300ms max (sheets,
  page transitions). Springs for anything the user drags or taps:
  `{ type: "spring", stiffness: 500, damping: 38 }` (snappy, no visible bounce);
  sheets `{ stiffness: 380, damping: 36 }`.
- **Only `transform` and `opacity`.** Never width, height, top, left or margin.
- **Reduced motion**: every animation goes through one `useMotionPrefs()` helper; with
  `prefers-reduced-motion: reduce`, moves become 120ms fades and the circuit loop is
  drawn complete with no pulse.
- Page transitions: 12px slide + fade on mobile, 150ms fade on desktop.
- Shared element: match card avatar and name → profile header (`layoutId`).
- Lists: first 8 cards fade and rise 8px, 30ms stagger. Later items appear instantly.
- Sheets/modals: spring open; on mobile drag down to dismiss (`@use-gesture/react`).
- Match cards: swipe right = ask for intro, left = skip, with visible buttons doing the
  same; the card follows the finger, a 1px signal line grows from the edge to show
  which action will fire.
- Circuit moment: the loop draws itself around the three avatars (600ms total, the one
  exception to the 300ms cap, split into three 200ms arcs, one per person). When all
  three accept, the loop closes and a single ring pulse expands once from the centre
  (300ms) and the status reads "Circuit active". No confetti.
- Micro: buttons scale to 0.97 on press; a verification badge pops (scale 0.8 → 1)
  when the level rises; connect, follow and apply are optimistic with an Undo toast
  (5 s).
- Skeletons shimmer (a translateX'd highlight); dashboard numbers count up once (mono
  digits keep the width stable).

## 9. Voice and tone

Plain, specific, human. Write like a helpful senior who knows the city. Indian context
without making a show of it: ₹, real cities and areas, real role names.

| Don't | Do |
| --- | --- |
| Unlock your potential | Ravi, 3 startups within 5 km are hiring backend interns |
| Seamless networking, AI-powered | Matched on what you need and what you can offer |
| No data found | No intro requests yet. When someone asks you to pass one on, it shows up here. |
| Error 500: something went wrong | We couldn't load your matches. Check your connection and try again. |
| Empower your journey | Add one project link. Founders look at work before college. |
| Successfully submitted! | Applied. Deepak at LedgerLoop usually replies within 3 days. |
| Users | People |
| Click here | Ask Lakshmi for an intro |

Numbers: `₹20,000/month`, `2.4 km`, `92% match`, Indian digit grouping for lakhs
(`₹4,50,000`). Dates: "Today", "Yesterday", then "3 Oct". Times: "4:30 pm".

Seed data: names from across India (Ravi Kumar, Meera Iyer, Asha Reddy, Arjun Mehta,
Nandini Rao…), specific roles ("Backend Engineering Intern", "Product Marketing
Lead"), stipends in ₹, real-sounding but fake startups on `.example` domains,
descriptions that say what the company actually does.

## 10. Banned

Purple/blue gradients, glassmorphism, glows, neon, blobs, aurora backgrounds; emoji as
icons or decoration; sparkles; "AI-powered" labels; hero clichés ("Unlock", "Revolutionise",
"Seamless", "Empower"); lorem ipsum, "John Doe", stock photos, placeholder logos;
everything centred; identical card grids everywhere; heavy drop shadows; rounded
everything; animation for decoration.

## 11. Per-screen intent (filled in as each screen is built)

Each screen states what the user is trying to do and its single most important element.

- **Home**: "What should I act on today?" → the top opportunity card.
- **Profile**: "Can I trust this person and what can we do for each other?" → for
  students, Proof of work; for founders, Needs and Offers.

## 12. PWA, performance, testing (carried over, still binding)

- Manifest, offline shell, update prompt, install prompt (unchanged; theme colours move
  to the new `bg` tokens).
- Initial JS under ~250 KB gzipped (`npm run size`); lazy-load map, charts, motion-heavy
  screens and the inbox. Virtualise long lists (`@tanstack/react-virtual`). Images lazy
  with fixed sizes.
- Slow 4G + mid-range Android; Lighthouse 90+ Performance and Accessibility; PWA checks
  in `e2e/pwa.spec.ts`.
- Keyboard and screen reader for everything; every swipe has a button.
- Playwright at 375px and 1280px for every demo story and every new feature.
