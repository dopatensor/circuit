import { DemoStories } from "../components/DemoStories";
import { Wordmark } from "../components/Shell";

const STEPS = [
  ["Say what you need and what you offer", "Paste a short bio; we suggest the rest."],
  ["Get matched across sectors", "A biotech founder can find the right deep-tech marketer."],
  ["Swap help in circuits", "You help one person, someone else helps you."],
];

export default function Welcome() {
  return (
    <main className="pt-safe mx-auto w-full max-w-6xl px-4 pb-16 md:px-10">
      <div className="grid gap-10 py-8 md:grid-cols-[1fr_1.1fr] md:gap-16 md:py-16">
        {/* The pitch. On laptops it stays in view while the stories scroll. */}
        <div className="flex flex-col gap-8 md:sticky md:top-16 md:self-start">
          <Wordmark />
          <div className="flex flex-col gap-4">
            <h1 className="text-display font-semibold tracking-tight">
              Match on what you <span className="text-blue">need</span> and what you can{" "}
              <span className="text-green">offer</span>.
            </h1>
            <p className="text-muted">
              Not on job titles or college names. Students find startups hiring nearby;
              founders, mentors and investors find each other across sectors.
            </p>
          </div>
          <ol className="flex flex-col gap-3">
            {STEPS.map(([title, line], i) => (
              <li key={title} className="flex gap-4 rounded-2xl border border-line bg-surface p-4">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-blue/50 text-sm font-semibold text-blue">
                  {i + 1}
                </span>
                <span className="flex flex-col">
                  <span className="font-medium">{title}</span>
                  <span className="text-sm text-muted">{line}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-sm font-medium tracking-wide text-muted uppercase">Try the demo</h2>
            <p className="text-muted">Pick a person from one of the five stories.</p>
          </div>
          <DemoStories />
        </div>
      </div>
    </main>
  );
}
