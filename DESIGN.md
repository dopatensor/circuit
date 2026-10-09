# Circuit — design system (redesign, R1–R7)

**Status: proposal v2, waiting for the user's OK (2026-10-09).** v1 (warm feed of cards)
was rejected as "a vibecoded LinkedIn knock-off". v2 takes **Bloomberg Terminal** and
**Notion** as references. The PWA, performance and testing rules at the end carry over
and still apply.

Approved dependencies: `motion`, `@tanstack/react-virtual`, `@use-gesture/react`.
Anything else: ask first. Icons are hand-drawn inline SVG; fonts are committed files.

## 1. The idea

**Opportunities as a terminal, people as documents.**

- **Bloomberg** gives us the *Brief* (home), Discover and the dashboard: dense, ranked
  tables you scan in seconds; a ticker of what moved in your city; watchlists and alerts;
  keyboard first (⌘K command bar, `G` then a letter to jump, `A` apply, `S` save); a
  status bar saying how fresh the data is. Numbers are the interface.
- **Notion** gives us profiles, startup pages and job pages: a calm document with a big
  title, a properties table (College, Based in, Open to, Verified…), then blocks, with
  **Proof of work as a database** (table or gallery view, expandable rows), callouts and
  toggles. You add work by pasting a link, like pasting into Notion.
- What we never do: a social feed of cards, follower counts, likes, a "post something"
  box. That's the LinkedIn shape, and it's what made v1 look generic.

## 2. Colour

Two themes with their own character, same tokens:

- **Terminal** (dark): near-black panels, amber accent. Feels like a trading desk.
- **Paper** (light): Notion-white page, a deeper amber. Feels like a document.

| Token | Paper (light) | Terminal (dark) | Used for |
| --- | --- | --- | --- |
| `bg` | `#FBFAF8` | `#0B0B0A` | Page |
| `panel` | `#FFFFFF` | `#121211` | Panels, tables, sheets |
| `raised` | `#F3F1ED` | `#1B1B19` | Tags, chips, callouts, inputs |
| `line` / `line2` | `#E7E4DE` / `#D6D2CA` | `#272724` / `#3A3A36` | Rules; input and button borders |
| `fg` | `#2B2A27` | `#E9E6DF` | Text |
| `fg2` | `#55524C` | `#BDB8AE` | Secondary text, sparklines |
| `muted` | `#6E6A63` | `#8E897F` | Labels, meta |
| `accent` | `#A35A00` | `#F2A33A` | Primary action, selected row marker, active tab |
| `ink` | `#FFFFFF` | `#1A1000` | Text on accent |
| `signal` | `#0A6B82` | `#5CC6D9` | Bridge matches, circuits, the connecting line. Nothing else |
| `signal-bg` | `#E2F1F4` | `#0F2A30` | Bridge tag background |

All AA (WCAG formula): `fg` ≥ 12.7:1; `muted` ≥ 4.5:1 on every surface; amber text
≥ 4.63:1 (paper) and ≥ 8.28:1 (terminal); text on amber 5.22:1 / 9.01:1; signal ≥ 5.41:1.

Rules: one amber button per view. Up and down movement uses ▲ ▼ glyphs in neutral text,
not green and red, so colour keeps its two meanings. Red only for errors.

## 3. Typography: IBM Plex

- **IBM Plex Sans** 400/600 for text, **IBM Plex Mono** 400/500 for data. A single
  family that was designed for technical interfaces; it reads as "terminal" in mono and
  "document" in sans. (Plex Sans Devanagari exists if we add Hindi later.)
- Self-hosted WOFF2, Latin plus `₹ ▲ ▼ → ·`, preloaded 400. About 70 KB for all four
  files; the mono files are subset to the characters tables need.
- **Mono is for data**: scores, counts, distances, pay, dates in tables, the ticker,
  column headers and section labels (uppercase, +0.06em), keyboard hints. **Sans is for
  language**: names, titles, sentences.
- Scale (px): 11 mono labels · 12 meta · 13 dense table text (desktop) · 14 body desktop ·
  15 body mobile · 16 panel titles · 18 section headings · 26/32 page titles.

## 4. Space, shape, density

- 4px base, 8px rhythm. Table rows 44px desktop with a 7px cell padding; 64px+ on mobile.
- **Square-ish**: panels 6px radius, buttons and tags 3–4px, bottom sheet 12px top
  corners. People avatars are circles, startups 4px squares. No pills.
- Borders, never shadows (only the bottom sheet's scrim darkens the page).
- Desktop is information-dense like a tool; mobile is one ranked list with the top item
  expanded, like Kite's watchlist.

## 5. Layout and navigation

- **Desktop (≥1200px)**: Notion-style left sidebar (232px): you and your role at the top,
  nav with keyboard hints, **Watchlist** (followed startups with what changed) and
  **Alerts** (saved searches with new-match counts), main action pinned at the bottom.
  Main area: command bar → ticker → workspace panels → status bar. Profiles and other
  pages are documents centred at 760px with a breadcrumb.
  _This replaces the brief's "centre 680px + right rail" on the Brief screen._ The right
  rail's content moves into panels (Selected item, Skills market) and the sidebar
  (watchlist, alerts); profile strength becomes a callout on your own profile.
- **Tablet (768–1199px)**: sidebar collapses to icons; the Selected panel becomes a
  sheet.
- **Mobile**: top bar (title, search, notifications, your avatar → Me), ticker,
  segmented filter, ranked list. Bottom bar: **Brief · Discover · [action] · Circuits ·
  Inbox**, centre action per role (student "Jobs", founder "Post", mentor/investor
  "Offer", partner admin "Gaps").
- **⌘K command bar** searches people, startups, jobs and skills, and runs commands
  (`jobs backend <5km`, `intro kavya`, `watch ledgerloop`). Search icon on mobile opens
  the same thing full screen.

## 6. Screens and their one job

- **Brief** (home): "What changed that I should act on?" → the ranked **Opportunities**
  table with a **Selected** panel that explains the top row (properties, why you match,
  actions with keyboard keys). Plus **Skills market** (demand vs supply near you,
  7-day change, 30-day sparkline) and the city **ticker**.
- **Profile**: "Can this person do the work?" → **Proof of work** database. Above it:
  activity strip (real commit activity from linked repos, not decoration), title,
  one-line bio, properties. Founders' profiles lead with **Needs / Offers** as a
  database instead.
- **Add work** sheet: paste a link → we detect the kind and show what we found, with an
  ownership check, then "What did you do?" and "Skills this proves".

## 7. Proof of work (new feature)

| Kind | What we fetch or ask | Check |
| --- | --- | --- |
| GitHub repo | name, description, languages, stars, commits in 90 days, your share of commits, last push | Repo owner (or a commit author) matches your linked GitHub account |
| Live app / website | page title, favicon | Add a `circuit-verify` meta tag or DNS TXT, or skip (shown as "unverified") |
| Kaggle, Hugging Face, Figma, Play Store, Behance | title, owner handle, one headline number (medal, downloads, likes) | Owner handle matches the account you link |
| Case study / anything else | your write-up | A rating from the person you did it for (founder endorsement) |

- Every item links to skills; skill chips show **evidence counts** ("Backend L3 · 3 proofs")
  and the match explanation cites them ("2 proofs").
- Founders see "Deepak opened your repo" signals (counts only, no tracking pixels).
- Backend uses `httpx` (already a dependency) to call the public GitHub API, with caching
  and a timeout; seed data ships with cached results so demos work offline and without
  rate limits. A GitHub token in `.env` is optional.

## 8. The connecting line

1px `signal` line, only where two real things are connected: the circuit loop, the
warm-intro path, a match score to its reason ("why you match"), the Bridge tag glyph,
and the ownership check on a proof. Never decoration.

## 9. Motion

Fast and mechanical, like a good terminal: 120–200ms, 300ms max; springs only for things
you drag. Only `transform` and `opacity`. Reduced motion → instant or 120ms fades.

- Selected panel cross-fades its content as you move with ↑/↓ (no sliding).
- Ticker scrolls only on hover/touch or when new data arrives (a single tick), never on
  a loop.
- New rows flash their background once (`sel` colour, 600ms fade) when data refreshes.
- Numbers that change count to the new value (mono keeps the width fixed).
- Sheets spring open and drag to dismiss; swipe a mobile opportunity row right to save
  or apply, left to skip, with buttons always present.
- Circuit moment (signature): the loop draws itself through the three avatars, one
  arc per person; when all three accept, it closes and pulses once. No confetti.
- Optimistic connect / follow / watch / apply with an Undo toast.

## 10. Voice

Terse and specific, like a good analyst's note. Indian context throughout.

| Don't | Do |
| --- | --- |
| Unlock your potential | 3 backend internships within 5 km opened this week |
| AI-powered matching | Both skills they ask for, at a higher level |
| No data found | Nothing new since this morning. Your alerts will flag new roles. |
| Something went wrong | Couldn't refresh. Showing data from 09:41. |
| Add a post | Add work: paste a GitHub, Figma, Kaggle or Play Store link |

Formats: `₹20,000/month`, `₹6.5L/yr`, `1.1 km`, `2d`, `09:41`, Indian digit grouping.

## 11. Banned

Purple/blue gradients, glassmorphism, glows, neon, blobs, aurora backgrounds; emoji
icons; sparkles; "AI-powered"; hero clichés; lorem ipsum, "John Doe", stock photos,
placeholder logos; everything centred; feeds of identical cards; heavy shadows;
rounded-everything; decorative animation; likes, follower counts, public posts.

## 12. PWA, performance, testing (carried over, still binding)

- Manifest, offline shell, update prompt, install prompt; theme colours from `bg`.
- Initial JS under ~250 KB gzipped (`npm run size`); lazy-load map, charts, motion-heavy
  screens and the inbox; virtualise long tables (`@tanstack/react-virtual`).
- Slow 4G + mid-range Android; Lighthouse 90+ Performance and Accessibility; PWA checks
  in `e2e/pwa.spec.ts`.
- Every table is a real `<table>` with headers; every row action has a button; keyboard
  shortcuts never replace visible controls.
- Playwright at 375px and 1280px for every demo story and every new feature.
