import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type Schemas, unwrap } from "../api/client";
import { Page } from "../components/Shell";
import {
  Card,
  Empty,
  ErrorState,
  Eyebrow,
  Muted,
  PrimaryButton,
  Skeleton,
  Stat,
  Title,
} from "../components/ui";

const HeatMap = lazy(() => import("../map/HeatMap").then((m) => ({ default: m.HeatMap })));

// Chart colours: the brand accents. Needs are demand (orange), offers blue; both pass
// 3:1 against the card surface and stay apart for colour-blind readers (orange vs blue).
const NEEDS = "#ff4f00";
const OFFERS = "#3b82f6";
const GRID = "var(--line)";
const MUTED = "var(--muted)";
const SHOWN = 10; // capabilities in the ranked chart

// Loading blocks the size of the real sections (phone / laptop), so nothing jumps
// when the data arrives.
const SIZE = {
  stats: "h-[122px] md:h-[102px]",
  gaps: "h-[678px] md:h-[630px]",
  map: "h-[594px] md:h-[678px]",
  intros: "h-[301px] md:h-[278px]",
};

/** Partner dashboard (F8): three numbers, what the ecosystem lacks (ranked and on the
 *  map), and whether cross-sector intros work. Plus "Run round now" for circuits. */
export default function Dashboard() {
  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Title>Dashboard</Title>
        <Muted>What your ecosystem has, and what it lacks.</Muted>
      </div>
      <Stats />
      <Gaps />
      <IntroSplit />
      <RunRound />
    </Page>
  );
}

function Stats() {
  const stats = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => unwrap(api.GET("/api/dashboard/stats")),
  });
  if (stats.isPending) return <Skeleton lines={1} className={SIZE.stats} />;
  if (stats.isError) return <ErrorState error={stats.error} retry={stats.refetch} />;
  const s = stats.data;
  return (
    <div className="grid grid-cols-3 gap-3" data-testid="dashboard-stats">
      <Stat value={s.members.toLocaleString()} label="Members" />
      <Stat value={s.startups_hiring.toLocaleString()} label="Startups hiring" />
      <Stat value={s.intros_accepted.toLocaleString()} label="Intros made" />
    </div>
  );
}

type Gap = Schemas["CapabilityGap"];

/** Ranked gaps (needs vs offers per capability), then where they are on the map. */
function Gaps() {
  const gaps = useQuery({
    queryKey: ["dashboard", "gaps"],
    queryFn: () => unwrap(api.GET("/api/dashboard/gaps", { params: { query: { limit: 100 } } })),
  });
  const [picked, setPicked] = useState<string | null>(null);

  if (gaps.isPending) {
    return (
      <>
        <Skeleton lines={1} className={SIZE.gaps} />
        <Skeleton lines={1} className={SIZE.map} />
      </>
    );
  }
  if (gaps.isError) return <ErrorState error={gaps.error} retry={gaps.refetch} />;
  const items = gaps.data.items;
  if (items.length === 0 || items.every((g) => g.needs === 0)) {
    return <Empty>No needs yet. Gaps appear once members say what they need.</Empty>;
  }
  const top = items.slice(0, SHOWN);
  const capability = picked ?? top[0].capability_id;
  return (
    <>
      <Card className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <Eyebrow>What your ecosystem lacks</Eyebrow>
          <p>
            The {top.length} biggest gaps between needs and offers. {top[0].name}:{" "}
            <strong>{top[0].needs} needs</strong>, {top[0].offers}{" "}
            {top[0].offers === 1 ? "offer" : "offers"}.
          </p>
        </div>
        <GapChart items={top} />
        <GapTable items={top} />
      </Card>
      <GapMap
        capabilities={items.filter((g) => g.needs > 0)}
        capability={capability}
        onPick={setPicked}
      />
    </>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-4 text-sm text-muted" aria-label="Legend">
      {[
        ["Needs", NEEDS],
        ["Offers", OFFERS],
      ].map(([label, color]) => (
        <li key={label} className="flex items-center gap-2">
          <span aria-hidden="true" className="size-3 rounded-sm" style={{ background: color }} />
          {label}
        </li>
      ))}
    </ul>
  );
}

function GapTooltip({ active, payload }: { active?: boolean; payload?: { payload: Gap }[] }) {
  if (!active || !payload?.length) return null;
  const g = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-raised px-3 py-2 text-sm shadow-lg">
      <p className="mb-1 text-muted">{g.name}</p>
      {[
        [g.needs, "needs", NEEDS],
        [g.offers, "offers", OFFERS],
      ].map(([value, label, color]) => (
        <p key={label as string} className="flex items-center gap-2">
          <span aria-hidden="true" className="h-0.5 w-3 rounded" style={{ background: color as string }} />
          <strong className="tabular-nums">{value}</strong>
          <span className="text-muted">{label}</span>
        </p>
      ))}
    </div>
  );
}

/** Horizontal bars, biggest gap at the top: needs (blue) next to offers (green). */
function GapChart({ items }: { items: Gap[] }) {
  const narrow = typeof window !== "undefined" && window.innerWidth < 640;
  const rowHeight = 40;
  return (
    <figure className="flex flex-col gap-3">
      <Legend />
      <div style={{ height: items.length * rowHeight + 32 }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={items}
            layout="vertical"
            margin={{ top: 0, right: 32, bottom: 0, left: 0 }}
            barGap={2}
            barCategoryGap={8}
            accessibilityLayer={false}
          >
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fill: MUTED, fontSize: 12 }}
              axisLine={{ stroke: GRID }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={narrow ? 112 : 168}
              tick={{ fill: MUTED, fontSize: 12 }}
              interval={0}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<GapTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
            <Bar dataKey="needs" fill={NEEDS} barSize={12} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList dataKey="needs" position="right" fill={MUTED} fontSize={12} />
            </Bar>
            <Bar dataKey="offers" fill={OFFERS} barSize={12} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList dataKey="offers" position="right" fill={MUTED} fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">
        Needs and offers per capability, biggest gap first. The same numbers are in the table.
      </figcaption>
    </figure>
  );
}

/** The chart's numbers as a table (for screen readers, and anyone who prefers them). */
function GapTable({ items }: { items: Gap[] }) {
  return (
    <details className="text-sm">
      <summary className="min-h-11 cursor-pointer content-center font-semibold text-fg underline underline-offset-2">
        Show as a table
      </summary>
      <table className="mt-2 w-full text-left">
        <thead className="text-muted">
          <tr>
            <th className="py-2 font-medium">Capability</th>
            <th className="py-2 text-right font-medium">Needs</th>
            <th className="py-2 text-right font-medium">Offers</th>
            <th className="py-2 text-right font-medium">Gap</th>
          </tr>
        </thead>
        <tbody>
          {items.map((g) => (
            <tr key={g.capability_id} className="border-t border-line">
              <td className="py-2">{g.name}</td>
              <td className="py-2 text-right tabular-nums">{g.needs}</td>
              <td className="py-2 text-right tabular-nums">{g.offers}</td>
              <td className="py-2 text-right tabular-nums">{g.gap}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** Where a capability is missing: a heat layer of grid cells, weighted by gap. */
function GapMap({
  capabilities,
  capability,
  onPick,
}: {
  capabilities: Gap[];
  capability: string;
  onPick: (id: string) => void;
}) {
  const [noMap, setNoMap] = useState(false);
  // The map library is big: load it only when the map is about to scroll into view.
  const box = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const el = box.current;
    if (!el || near) return;
    if (!("IntersectionObserver" in window)) return setNear(true);
    const io = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setNear(true),
      { rootMargin: "200px" },
    );
    io.observe(el);
    return () => io.disconnect();
  });
  const areas = useQuery({
    queryKey: ["dashboard", "areas", capability],
    queryFn: () =>
      unwrap(api.GET("/api/dashboard/gaps/areas", { params: { query: { capability } } })),
    placeholderData: (previous) => previous, // keep the old heat while the new one loads
  });
  const name = capabilities.find((c) => c.capability_id === capability)?.name ?? capability;
  const hot = areas.data?.cells.filter((c) => c.gap > 0) ?? [];
  const cells = useMemo(() => {
    const max = Math.max(areas.data?.max_gap ?? 0, 1);
    return hot.map((c) => ({ lat: c.lat, lng: c.lng, weight: c.gap / max }));
  }, [areas.data]);
  const center = cells.length
    ? {
        lat: cells.reduce((s, c) => s + c.lat, 0) / cells.length,
        lng: cells.reduce((s, c) => s + c.lng, 0) / cells.length,
      }
    : { lat: 12.9716, lng: 77.5946 };

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Eyebrow>Where it's missing</Eyebrow>
        <p>Brighter areas have more people needing this than offering it nearby.</p>
      </div>
      <label className="flex flex-col gap-2">
        <span className="text-sm text-muted">Capability</span>
        <select
          value={capability}
          onChange={(e) => onPick(e.target.value)}
          className="min-h-11 rounded-xl border border-line bg-raised px-3"
        >
          {capabilities.map((c) => (
            <option key={c.capability_id} value={c.capability_id}>
              {c.name} ({c.gap > 0 ? `gap ${c.gap}` : "no gap"})
            </option>
          ))}
        </select>
      </label>
      {areas.isError ? (
        <ErrorState error={areas.error} retry={areas.refetch} />
      ) : areas.isPending ? (
        <Skeleton lines={1} className="h-[23.5rem] md:h-[30rem]" />
      ) : (
        <>
          <p role="status" className="text-sm" data-testid="gap-areas">
            {hot.length === 0
              ? `No area is short of ${name.toLowerCase()} right now.`
              : `${name}: ${hot.length} ${hot.length === 1 ? "area" : "areas"} (about ${areas.data.cell_km} km across) with more needs than offers.`}
          </p>
          {noMap ? (
            <p className="text-sm text-muted">This device can't draw the map.</p>
          ) : (
            <div
              ref={box}
              className={`relative h-80 overflow-hidden rounded-xl border border-line md:h-[28rem] ${
                areas.isFetching ? "opacity-60" : ""
              }`}
              role="img"
              aria-label={`Map of where ${name.toLowerCase()} is missing`}
            >
              {near ? (
                <Suspense fallback={<div className="h-full animate-pulse bg-raised" />}>
                  <HeatMap center={center} cells={cells} onUnavailable={() => setNoMap(true)} />
                </Suspense>
              ) : (
                <div className="h-full bg-raised" />
              )}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

/** Intro acceptance, local vs bridge (cross-sector) matches. */
function IntroSplit() {
  const intros = useQuery({
    queryKey: ["dashboard", "intros"],
    queryFn: () => unwrap(api.GET("/api/dashboard/intros")),
  });
  if (intros.isPending) return <Skeleton lines={1} className={SIZE.intros} />;
  if (intros.isError) return <ErrorState error={intros.error} retry={intros.refetch} />;
  const rows: [string, string, Schemas["AcceptanceGroup"], string][] = [
    ["Local matches", "same sector or nearby", intros.data.local, "var(--muted)"],
    ["Bridge matches", "across sectors", intros.data.bridge, "var(--signal)"],
  ];
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Eyebrow>Do bridge intros work?</Eyebrow>
        <p>How often an intro request is accepted.</p>
      </div>
      <ul className="flex flex-col gap-4" data-testid="intro-split">
        {rows.map(([label, hint, g, color]) => {
          const pct = g.rate === null ? null : Math.round(g.rate * 100);
          return (
            <li key={label} className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between gap-3">
                <span>
                  <span className="font-semibold">{label}</span>{" "}
                  <span className="text-sm text-muted">{hint}</span>
                </span>
                <span className="text-xl font-semibold">{pct === null ? "–" : `${pct}%`}</span>
              </div>
              <div className="h-3 rounded-full bg-raised" aria-hidden="true">
                <div
                  className="h-3 rounded-full"
                  style={{ width: `${pct ?? 0}%`, background: color }}
                />
              </div>
              <span className="text-sm text-muted">
                {g.decided === 0
                  ? "No answers yet."
                  : `${g.accepted} of ${g.decided} accepted`}
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

/** The weekly circuit round, on demand (for demos). */
function RunRound() {
  const queryClient = useQueryClient();
  const run = useMutation({
    mutationFn: () => unwrap(api.POST("/api/admin/circuits/run")),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["circuits"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
  });
  const r = run.data;
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Eyebrow>Exchange circuits</Eyebrow>
        <p>Find loops of three people who can each help the next, and propose them now.</p>
      </div>
      <PrimaryButton className="self-start" disabled={run.isPending} onClick={() => run.mutate()}>
        {run.isPending ? "Running…" : "Run round now"}
      </PrimaryButton>
      {run.isError && <ErrorState error={run.error} />}
      {r && (
        <div role="status" className="flex flex-col gap-3" data-testid="round-result">
          <p className="text-sm text-muted">
            Round {r.round_key}: {r.pool} people could exchange help, {r.cycles_found} possible{" "}
            {r.cycles_found === 1 ? "loop" : "loops"}.{" "}
            {r.circuits.length === 0
              ? "No new circuits this time (people already in a circuit are left out)."
              : `${r.circuits.length} proposed. Each person has 72 hours to accept.`}
          </p>
          {r.circuits.length > 0 && (
            <ul className="flex flex-col gap-2">
              {r.circuits.map((c, i) => (
                <li key={c.id ?? i} className="rounded-xl border border-line bg-raised px-4 py-3">
                  {c.sentence}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}
