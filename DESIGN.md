# Circuit — design system (redesign, R1–R7)

**Status: v3 approved by the user (2026-10-09). R1 and R2 are built; see "Decisions made in R1" and "Decisions made in R2" at the end.**
History: v1 (warm card feed) looked like a LinkedIn knock-off; v2 (Bloomberg + Notion)
was too much for a student. v3 is **simple, calm and guided**: every screen follows the
same structure, and the app always tells you the next step.

The PWA, performance and testing rules at the end are carried over and still binding.
Approved dependencies: `motion`, `@tanstack/react-virtual`, `@use-gesture/react`.
Anything else: ask first. Icons are inline SVG; fonts are committed files.

## 1. Principles

1. **One next step.** Every person always sees one clear thing to do next, with one
   amber button. Students get a path (Profile → Proof → Apply → Interview); founders get
   theirs (Startup → Needs → Matches → Intros).
2. **Same structure everywhere.** Learn one screen, know them all (section 3).
3. **Show work, not titles.** Profiles lead with proof of work: GitHub repos, live
   links, ratings from people you helped.
4. **Quiet by default.** Neutrals, generous spacing, one accent. No feeds, likes,
   follower counts, tickers or dashboards for students.

## 2. Look

**Colour** (light is the default; dark mode follows the system):

| Token | Light | Dark | Job |
| --- | --- | --- | --- |
| `bg` | `#FBFAF8` | `#111110` | Page |
| `panel` | `#FFFFFF` | `#191917` | Cards, sheets |
| `raised` | `#F3F1ED` | `#22221F` | Tags, chips, inputs |
| `line` / `line2` | `#E7E4DE` / `#D6D2CA` | `#2A2A27` / `#3D3D39` | Borders |
| `fg` / `fg2` / `muted` | `#2B2A27` / `#55524C` / `#6E6A63` | `#ECE9E2` / `#C2BDB3` / `#948F85` | Text |
| `accent` | `#A35A00` | `#F2A33A` | The one primary button per screen, the current step, unread counts |
| `signal` | `#0A6B82` | `#5CC6D9` | Only Bridge matches and circuits |

All text pairs pass WCAG AA (muted ≥ 4.5:1 on every surface; white on amber 5.2:1).

**Type:** IBM Plex Sans 400/600 for everything; IBM Plex Mono 500 only for match
scores and big numbers. Sizes: 12 · 14 · 16 (body) · 18 (section) · 28 (page title).
Left-aligned.

**Space and shape:** 8px grid; 20px phone gutter, 40px desktop. Cards 12px radius with
a 1px border, no shadows. Buttons 8px, tags 4px. People are circles, startups rounded
squares.

**The line:** a thin line connects real steps or people only: the path stepper, the
warm-intro path, the circuit loop. Never decoration.

## 3. Page structure (every screen)

```
Title                     one plain sentence saying what this page is for
[ The one thing ]         the next step, the job, the person: one card, one amber button
Section heading   See all a short list (3–5 rows) of what's next most useful
Section heading   See all another short list
```

- Lists are rows inside one bordered card, not a grid of cards. Each row: avatar or logo,
  title, one meta line, one "why" line, and a number on the right if it matters.
- Empty, loading and error states keep the same structure (skeleton rows, one helpful
  sentence, one button).

## 4. Navigation

- **Phone:** top bar (title, search, notifications, your avatar → Me). Bottom bar:
  **Home · Discover · [main action] · Circuits · Inbox**. Centre action: student
  "Jobs", founder "Post", mentor/investor "Offer help", partner admin "Gaps".
- **Tablet and laptop (≥768px):** left sidebar (the same destinations plus Me, the
  main action as a button, you at the bottom), content column up to 640px.
  **Wide (≥1280px):** plus a right rail with **Profile strength as a checklist** and
  "People worth meeting" (students: "Jobs near you"). Below 1280px, Home shows profile
  strength under the content instead. Search (Ctrl/⌘K) arrives in R4.

## 5. Key screens

| Screen | What the person wants | The one thing |
| --- | --- | --- |
| Home | "What should I do this week?" | Path card with the next step |
| Profile | "Can this person do the work?" | Proof of work |
| Add work | "Show something I built" | 3 steps: paste link → check it → describe |
| Job | "Should I apply?" | Why you match + Apply |
| Circuits | "Will I join this loop?" | The loop of three people + Accept |
| Inbox | "Who wrote to me?" | Unread conversations |

## 6. Proof of work (built in R2; CLAUDE.md F12)

Two kinds, always labelled so nobody confuses them:

| Kind | How it gets in | We show | Label |
| --- | --- | --- | --- |
| GitHub | "Connect GitHub" (OAuth, no scopes, public data only). Never a typed username | Featured repos (the student picks up to 6, can hide any): languages, frameworks, how many commits are theirs, README line, homepage. Merged pull requests to other people's projects. Recent activity | **Verified by GitHub** chips (GitHub mark + skill + evidence, e.g. "Backend development · Python, FastAPI") |
| Other work | "Add work": a portfolio, Behance or Dribbble link, a live site, or a case study (no link, a write-up of 40+ characters) | Title, kind, write-up, the skills it shows | **Added by you** |

- Stars and follower counts are never shown or used.
- A GitHub link added as "other work" stays a plain "Code link"; only the connection
  verifies.
- Skill chips on a profile carry the GitHub mark when GitHub verifies that skill.
- Disconnect is one button and a confirmation; it deletes every imported repo.
- Seed data ships with saved results (Ravi's GitHub, Sneha's portfolio), so demos work
  offline and never call GitHub.

## 7. Motion

Short and purposeful: 150–250ms, springs only for things you drag, only transform and
opacity, everything off or a simple fade with reduced motion.

- Path stepper: the line fills to the next step when one is completed.
- Lists: the first few rows fade up once on first load.
- Sheets: slide up, drag down to close.
- Connect, follow, apply: instant, with an Undo toast.
- Circuit moment: the loop draws through the three avatars; when all accept, it closes
  with one gentle pulse.

## 8. Voice

Plain and kind, like a senior who wants you to get the job.

| Don't | Do |
| --- | --- |
| Unlock your potential | Here's what to do this week. |
| AI-powered matching | You have both skills they asked for. |
| No results found | No matches yet. Add one project and we'll look again. |
| Error occurred | Couldn't load this. Check your connection and try again. |

Indian context: ₹20,000/month, ₹6.5 lakh/year, real areas and colleges.

## 9. Banned

Gradients, glassmorphism, glows, neon, blobs; emoji icons, sparkles, "AI-powered";
hero clichés; lorem ipsum, stock photos; likes, follower counts, public posts; heavy
shadows; tickers and dense data tables on student screens; decorative animation.

## 10. PWA, performance, testing (carried over, binding)

- Manifest, offline shell, update prompt, install prompt.
- Initial JS under ~250 KB gzipped (`npm run size`); lazy-load map, charts, motion-heavy
  screens and inbox; virtualise long lists.
- Lighthouse 90+ Performance and Accessibility on Slow 4G mobile; PWA checks in
  `e2e/pwa.spec.ts`.
- Keyboard and screen reader for everything; swipe actions always have buttons.
- Playwright at 375px and 1280px for every demo story and new feature.

## Decisions made in R1 (2026-10-09)

- **Navigation:** Home · Discover · [main action] · Circuits · Inbox on phones, with Me on
  your avatar in the top bar (the user didn't pick the alternative). The sidebar lists
  the same places plus Me. Old URLs (`/map`, `/jobs`, `/matches`, `/startups`,
  `/intros`) keep working: the first four are Discover's tabs, `/intros` redirects to
  `/inbox`.
- **Discover tabs (until R4 adds People search):** Matches · Jobs · Startups · Map
  (students start on Map; partner admins have no Matches tab).
- **Inbox (until R5 adds messages):** the intro requests screen.
- **Centre actions:** student "Jobs" → `/jobs`; founder "Post" → a sheet with "Post a
  job" (new `/jobs/new` form) or "Update what you need"; mentor/investor "Offer" →
  `/me/profile`; partner admin "Gaps" → `/dashboard`.
- **Home's path for students** was Profile → Apply → Shortlist in R1; R2 made it
  Profile → Proof → Apply → Interview.
- **Status colours on older screens:** good news ("accepted", "hiring") is an outlined
  neutral badge; "in progress" is the amber tint. Map pins: amber for hiring, grey
  otherwise (pins must be coloured by hiring status, F2).
- **Dashboard chart and heat colours** still use the Phase 11 blue/green pair (grid and
  label colours now follow the theme). They get a proper two-theme check with the
  dataviz validator in R6.
- **API addition:** `StartupLink.is_claimer`, so the app knows which startups you can
  post jobs for (being on a team isn't enough).
- **Bundle:** first-load JavaScript is ~140 KB gzipped (budget raised to 250 KB, per the
  redesign brief); `motion` uses LazyMotion with the small DOM feature set.

## Decisions made in R2 (2026-10-09)

- **Proof of work page** `/me/proof` (students): the GitHub card is the one thing
  (Connect, or the connection with its verified skills and Disconnect), then "Your
  repos" (Feature / Hide per row; hiding has an Undo toast), then "Other work" with
  "Add work" (a bottom sheet: link, title, write-up, up to 5 skill chips).
- **GitHub callback** `/me/github/callback`: shows a loading block while the API
  checks the code; "You didn't give access" if the student said no on GitHub.
- **Profiles** `/people/:id` for everyone: students lead with proof of work, then
  skills; founders, mentors and investors show what they can help with, what they're
  looking for, and their startups. Applicants' names link to their profiles.
- **Me** (students): a "Proof of work" card (Manage), and "Privacy": "Show my college
  on my profile" and "See your profile as others see it" (every role but partner
  admins).
- **Profile strength** for students adds "Show proof of work" as the third item.
- **Applicants** show "Verified by GitHub" chips and other proof under the skills;
  the list is ordered by skill match plus proof (`rank_score`), never by college.
- **Not built in R2:** recognising Kaggle, Hugging Face, Figma and Play Store links
  with a headline number, and "verification tag on the site" for websites (both in
  the v3 table). Those links are accepted as "other work" for now.
