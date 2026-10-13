import { type ReactNode, useState } from "react";
import {
  Avatar,
  Badge,
  BottomSheet,
  BridgeBadge,
  Button,
  Card,
  Checklist,
  Chip,
  EmptyState,
  ErrorBlock,
  HiringBadge,
  ICON_NAMES,
  Icon,
  IconButton,
  List,
  ListRow,
  Modal,
  RemovableChip,
  Score,
  Section,
  SkeletonBlock,
  SkeletonRows,
  Stepper,
  Tabs,
  VerificationBadge,
  useToast,
} from "../components/ds";
import { Wordmark } from "../components/Shell";

// /design: every building block of the design system (dev and demo
// builds only). DESIGN.md explains the rules; this page shows them.

const TOKENS: [string, string][] = [
  ["bg", "#000000"],
  ["panel", "#0B0B0B"],
  ["raised", "#161616"],
  ["line", "#222222"],
  ["line2", "#333333"],
  ["fg", "#F4F4F0"],
  ["fg2", "#C4C4BE"],
  ["muted", "#8C8C86"],
  ["accent", "#CCFF00"],
  ["signal", "#3B82F6"],
  ["hot", "#FF4F00"],
  ["danger", "#FF5C8A"],
];

function Block({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  const id = `ds-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4 border-t border-line pt-8">
      <div>
        <h2 id={id} className="text-lg font-semibold">
          {title}
        </h2>
        {note && <p className="mt-1 max-w-[60ch] text-sm text-fg2">{note}</p>}
      </div>
      {children}
    </section>
  );
}

export default function Design() {
  const [sheet, setSheet] = useState(false);
  const [modal, setModal] = useState(false);
  const [tab, setTab] = useState<"people" | "startups" | "jobs">("people");
  const [chips, setChips] = useState<string[]>(["Backend development"]);
  const [step, setStep] = useState(1);
  const [level, setLevel] = useState(1);
  const [saved, setSaved] = useState(false);
  const toast = useToast();

  return (
    <div className="mx-auto flex max-w-[880px] flex-col gap-10 px-5 py-8 md:px-10 md:py-12">
      <header className="flex flex-col gap-4">
        <Wordmark />
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.015em]">Design system</h1>
          <p className="mt-1 max-w-[60ch] text-fg2">
            The building blocks every screen uses. Simple, calm and guided: one lime action per screen, blue only for
            Bridge matches and circuits, neutrals for everything else.
          </p>
        </div>
      </header>

      <Block title="Colour" note="Pitch black with three accents from the logo. Every text pair passes WCAG AA. Lime means 'do this'; blue means 'cross-sector or circuit'; orange means demand (hiring, needs, gaps).">
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {TOKENS.map(([name, hex]) => (
            <li key={name} className="flex items-center gap-3">
              <span className="size-10 shrink-0 rounded-lg ring-1 ring-line2" style={{ background: `var(--${name})` }} />
              <span className="flex flex-col">
                <span className="text-sm font-semibold">{name}</span>
                <span className="text-xs text-muted">{hex}</span>
              </span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Type" note="IBM Plex Sans for words, IBM Plex Mono only for standalone numbers.">
        <div className="flex flex-col gap-3">
          <p className="text-2xl font-semibold tracking-[-0.015em]">28 · Page title</p>
          <p className="text-xl font-semibold">22 · Card title</p>
          <p className="text-lg font-semibold">18 · Section heading</p>
          <p className="text-base">16 · Body text. Plain and kind, like a senior who wants you to get the job.</p>
          <p className="text-sm text-fg2">14 · Secondary text and meta lines</p>
          <p className="text-xs font-semibold tracking-[0.06em] text-muted uppercase">12 · Label</p>
          <p className="num text-display">100%</p>
        </div>
      </Block>

      <Block title="Spacing and shape" note="8px grid. Cards 12px radius with a 1px border, buttons 8px, chips 6px, badges 4px.">
        <div className="flex flex-wrap items-end gap-4">
          {[4, 8, 12, 16, 24, 32, 48].map((n) => (
            <div key={n} className="flex flex-col items-center gap-2">
              <span className="block bg-accent" style={{ width: n, height: n }} />
              <span className="text-xs text-muted">{n}</span>
            </div>
          ))}
        </div>
      </Block>

      <Block title="Icons" note="Drawn inline on a 24px grid. Always next to a text label, or with an accessible name.">
        <ul className="grid grid-cols-4 gap-3 sm:grid-cols-6 md:grid-cols-8">
          {ICON_NAMES.map((n) => (
            <li key={n} className="flex flex-col items-center gap-1.5 rounded-lg border border-line py-3">
              <Icon name={n} />
              <span className="text-[10px] text-muted">{n}</span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Buttons" note="One primary button per screen. Pressing scales to 97% (off with reduced motion).">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary">Apply now</Button>
          <Button>See the job</Button>
          <Button variant="ghost">Skip</Button>
          <Button variant="danger">Withdraw</Button>
          <Button variant="primary" disabled>
            Sending…
          </Button>
          <IconButton icon="share" label="Share" />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" icon="plus">
            Small
          </Button>
          <Button icon="briefcase">Medium</Button>
          <Button size="lg" variant="primary">
            Large
          </Button>
        </div>
      </Block>

      <Block title="Avatars" note="Initials, never photos. People are circles; startups are rounded squares.">
        <div className="flex flex-wrap items-end gap-4">
          {([24, 32, 40, 56, 72] as const).map((s) => (
            <Avatar key={s} name="Ravi Kumar" size={s} />
          ))}
          {([32, 40, 56] as const).map((s) => (
            <Avatar key={`s${s}`} name="LedgerLoop" size={s} kind="startup" />
          ))}
        </div>
      </Block>

      <Block title="Badges" note="Verification levels, Bridge and Hiring. When a level goes up, the badge pops once.">
        <div className="flex flex-wrap items-center gap-2">
          {[0, 1, 2, 3].map((l) => (
            <VerificationBadge key={l} level={l} />
          ))}
          <BridgeBadge />
          <BridgeBadge detail="deep tech ↔ biotech" />
          <HiringBadge hiring />
          <HiringBadge hiring={false} />
          <Badge tone="accent">Shortlisted</Badge>
          <Badge icon="github">ravik-dev</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span data-testid="pop-demo">
            <VerificationBadge level={level} />
          </span>
          <Button size="sm" onClick={() => setLevel((l) => (l >= 3 ? 1 : l + 1))}>
            {level >= 3 ? "Reset level" : "Raise level"}
          </Button>
        </div>
      </Block>

      <Block title="Chips" note="Tap to select. Selected chips get an outline and a tick, so the state never depends on colour alone.">
        <div className="flex flex-wrap gap-2">
          {["Backend development", "Data engineering", "Marketing", "Regulatory affairs"].map((c) => (
            <Chip
              key={c}
              selected={chips.includes(c)}
              onToggle={() => setChips((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]))}
            >
              {c}
            </Chip>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip detail="3 proofs">Backend development</Chip>
          <RemovableChip onRemove={() => toast({ message: "Filter removed" })}>Within 5 km</RemovableChip>
        </div>
      </Block>

      <Block title="Cards and lists" note="Lists are rows inside one bordered card, not a grid of cards.">
        <Section title="Matches for you" action={{ label: "See all", to: "/design" }}>
          <List label="Example matches">
            <ListRow
              leading={<Avatar name="LedgerLoop" kind="startup" />}
              title="Backend Engineering Intern"
              meta="LedgerLoop · 1.1 km · ₹20,000/month"
              why="Has both skills they need: backend and data engineering"
              trailing={<Score value={100} />}
            />
            <ListRow
              leading={<Avatar name="Kavya Menon" />}
              title="Kavya Menon"
              meta="Mentor · deep tech"
              why={
                <span className="flex flex-col items-start gap-1.5">
                  You both sell into long sales cycles to technical buyers.
                  <BridgeBadge />
                </span>
              }
              trailing={<Score value={87} />}
            />
          </List>
        </Section>
        <Card>
          <p className="font-semibold">A card</p>
          <p className="mt-1 text-sm text-fg2">Panel background, 1px border, 12px corners. No shadow.</p>
        </Card>
      </Block>

      <Block title="Path stepper" note="The line connects real steps. It fills (a scale transform) when a step is done.">
        <Card className="flex flex-col gap-4">
          <Stepper steps={["Profile", "Proof", "Apply", "Interview"]} current={step} label="Example path" />
          <div className="flex gap-2">
            <Button size="sm" onClick={() => setStep((s) => Math.max(0, s - 1))}>
              Back a step
            </Button>
            <Button size="sm" onClick={() => setStep((s) => Math.min(4, s + 1))}>
              Complete a step
            </Button>
          </div>
        </Card>
      </Block>

      <Block title="Checklist" note="Profile strength: what's done, and the next step in bold.">
        <Card className="max-w-sm">
          <Checklist
            title="Profile strength"
            items={[
              { label: "Add your skills", done: true },
              { label: "Write a short bio", done: true },
              { label: "Add one project", done: false, next: true },
              { label: "Verify a work or college email", done: false },
            ]}
          />
        </Card>
      </Block>

      <Block title="Tabs" note="Arrow keys move between tabs; the underline slides to the selected one.">
        <Tabs
          label="Example tabs"
          id="ds-tabs"
          tabs={[
            ["people", "People"],
            ["startups", "Startups"],
            ["jobs", "Jobs"],
          ]}
          value={tab}
          onChange={setTab}
        />
        <p role="tabpanel" aria-labelledby={`ds-tabs-${tab}`} className="text-sm text-fg2">
          Showing {tab}.
        </p>
      </Block>

      <Block title="Sheets, modals and toasts" note="Sheets slide up on phones (drag down to close) and are centred panels on laptops.">
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => setSheet(true)}>Open bottom sheet</Button>
          <Button onClick={() => setModal(true)}>Open modal</Button>
          <Button
            onClick={() => {
              setSaved(true);
              toast({ message: "Saved LedgerLoop's internship", action: { label: "Undo", onClick: () => setSaved(false) } });
            }}
          >
            {saved ? "Saved" : "Save a job"}
          </Button>
        </div>
        <BottomSheet open={sheet} onClose={() => setSheet(false)} title="Filters">
          <div className="flex flex-col gap-4">
            <p className="text-fg2">Show jobs within</p>
            <div className="flex flex-wrap gap-2">
              <Chip selected onToggle={() => {}}>
                5 km
              </Chip>
              <Chip onToggle={() => {}}>10 km</Chip>
              <Chip onToggle={() => {}}>20 km</Chip>
            </div>
            <Button variant="primary" onClick={() => setSheet(false)}>
              Show 12 jobs
            </Button>
          </div>
        </BottomSheet>
        <Modal open={modal} onClose={() => setModal(false)} title="Withdraw your application?">
          <p className="text-fg2">LedgerLoop won't see it any more. You can apply again later.</p>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setModal(false)}>
              Keep it
            </Button>
            <Button variant="danger" onClick={() => setModal(false)}>
              Withdraw
            </Button>
          </div>
        </Modal>
      </Block>

      <Block title="Loading, empty and error" note="Every screen has all three, in the same structure as the real content.">
        <SkeletonRows rows={2} label="Loading example" />
        <SkeletonBlock className="h-4 w-1/2" />
        <EmptyState icon="people" title="No matches yet" action={<Button size="sm">Update your profile</Button>}>
          Add what you need and what you can offer, and we'll look again.
        </EmptyState>
        <ErrorBlock error={new Error("x")} retry={() => toast({ message: "Trying again…" })} />
      </Block>
    </div>
  );
}
