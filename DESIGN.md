# Circuit — design and PWA brief (Phases 8–11)

Agreed with the user on 2026-10-07, on top of [CLAUDE.md](CLAUDE.md). Follow it for
every screen. The user approved `vite-plugin-pwa`, `openapi-fetch`, `@tailwindcss/vite`,
`react-router` and `@playwright/test` as dependencies (and Lighthouse for the score
script).

## Update (2026-10-07): the brief was loosened after the Phase 8 review

The first shell was too plain to show customers. The user asked to loosen the brief,
use **neon blue and green**, and use **pure black (#000000)**. This section overrides
the original design rules below wherever they conflict:

- **Dark only, pure black background** (`#000`). Cards are near-black (`#0c0d10`),
  raised elements `#15171c`, lines `#24262d`, text `#f4f6fa`, muted text `#9aa1ad`.
  (Light mode was dropped; neon colours don't work on white. Easy to bring back.)
- **Neon blue `#2f8cff`**: the main action on each screen (black text on it, soft glow),
  the active tab, focus rings, story numbers, avatar rings.
- **Neon green `#39ff8f`**: the "Bridge match" badge (with a glow), good news and
  positive statuses (hiring, accepted, role verified, "You").
- **Soft rounded cards** (`rounded-2xl`, 1px border) structure every screen, instead of
  hairline lists. Subtle glows are allowed on the main action and Bridge badge only.
- **Initials avatars** (a circle with a blue ring) for people; rounded squares for
  startups and jobs. Still no photos or decorative images, and no gradients.
- **Tinted status pills**: green, blue or grey backgrounds at 10% with matching text.
- **Four text sizes**: `text-sm`, `text-base`, `text-xl`, plus `text-display` (2.5rem)
  for the welcome headline and big numbers in stat tiles.
- Laptops: the sidebar shows who you are at the bottom; welcome uses two columns.
- Demo personas are grouped by the five stories, in the welcome page and in a "Switch
  person" sheet opened from Me.

## Design: hyper-minimalist, mobile-first (original brief)
- One idea per screen. If a screen needs explaining, it's too complex; simplify it.
- Mostly black and white, with one accent colour used only for the main action on each
  screen and for the "Bridge match" badge. Light and dark mode from system settings.
- One font family (system font stack, nothing to download), at most 3 text sizes
  (`text-sm`, `text-base`, `text-xl`; the others are disabled in `src/index.css`), and
  plenty of whitespace.
- No decorative images, gradients, shadows or animations beyond quick, subtle
  transitions. Respect "reduce motion".
- Text over icons where possible; any icon gets a text label.
- Design at 375px wide first, then expand to tablet and desktop.

## Layout
- Mobile: bottom tab bar with at most 4 tabs, chosen by role:
  - Student: Map · Jobs · Matches · Me
  - Founder / mentor / investor: Matches · Circuits · Intros · Me
  - Partner admin: Dashboard · Map · Intros · Me (Intros added in Phase 10: partner
    admins are often the mutual connection in a warm intro)
- Desktop: the same tabs as a slim left sidebar, content in a centred column with max
  width ~720px. The map and dashboard may use full width.
- Tap targets at least 44px; primary buttons within thumb reach at the bottom of mobile
  screens.
- The persona switcher (demo mode only) lives in the "Me" tab, not the main header.

## Screens (minimal versions)
- **Map**: full-screen map, one filter button opening a bottom sheet, pins coloured
  only by hiring or not hiring. Tapping a pin opens a bottom sheet with name, match %,
  open roles, and one button.
- **Jobs**: a plain list (title, startup, distance, match %), one search field and one
  filter button. Job page: role, skills needed (matched ones highlighted), and an
  "Apply" button fixed at the bottom.
- **Matches**: one card per match showing the name, one-line reason, Bridge badge if
  relevant, and one action.
- **Circuits**: the loop shown as three names in a simple circle, the three "who helps
  whom" lines, and Accept and Decline buttons.
- **Dashboard**: three big numbers at the top, then one ranked bar chart of capability
  gaps, then the gap map.
- Every screen has loading (skeletons, not spinners), empty and error states, each
  written in one plain sentence.

## PWA
- Manifest: name and short name "Circuit", standalone, theme and background colours
  matching the design, start URL that opens the user's main tab, icons at 192px, 512px
  and a maskable 512px, plus an apple-touch-icon. A simple text-only "C" icon.
- Service worker via vite-plugin-pwa: cache the app shell so it opens instantly and
  works offline. Network-first for API data; the last-loaded matches, jobs and
  applications are available offline, marked "Last updated <time>". Never cache auth
  tokens or other users' data.
- When a new version is deployed, show a small "Update available, tap to refresh" bar.
- A one-time, dismissible "Add Circuit to your home screen" prompt after the second
  visit. On iPhone, the short manual instructions (Share, then "Add to Home Screen").
- Respect safe areas (notch and home indicator) in standalone mode.
- All data through the generated OpenAPI client.

## Performance (budget phones, slow networks)
- Initial JavaScript under ~200KB gzipped (`npm run size` enforces it); lazy-load the
  map and dashboard charts.
- Test with "Slow 4G" and a mid-range Android profile (Lighthouse's mobile defaults).
- Lighthouse 90+ for Performance, Accessibility, Best Practices (and PWA checks, now
  covered by `e2e/pwa.spec.ts` because Lighthouse 12+ dropped that category).

## Tests
- Playwright tests for all demo stories at 375px and 1280px widths.
- A test that the manifest and service worker register correctly.
- Lighthouse as a script (`npm run lighthouse`), scores reported each phase.
