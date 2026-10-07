import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useCallback, useMemo, useState } from "react";
import { Link } from "react-router";
import { api, type Schemas, unwrap } from "../api/client";
import { useCapabilities } from "../api/hooks";
import { useAuth } from "../auth";
import { Sheet } from "../components/Sheet";
import {
  Empty,
  ErrorState,
  Pill,
  PrimaryButton,
  SecondaryButton,
  Skeleton,
} from "../components/ui";

// MapLibre is large, so it loads only when this screen opens.
const MapView = lazy(() => import("../map/MapView").then((m) => ({ default: m.MapView })));

type Startup = Schemas["MapStartup"];
type Filters = { hiringOnly: boolean; capability: string; radiusKm: number };

const ZOOM: Record<number, number> = { 5: 12.5, 10: 11.5, 20: 10.5, 50: 9.5 };

export default function MapScreen() {
  const { member } = useAuth();
  const student = member?.role === "student";
  const [filters, setFilters] = useState<Filters>({
    hiringOnly: false,
    capability: "",
    radiusKm: student ? 10 : 50, // distance is a hard filter for students
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [noMap, setNoMap] = useState(false);

  const startups = useQuery({
    queryKey: ["map", filters],
    queryFn: () =>
      unwrap(
        api.GET("/api/map/startups/nearby", {
          params: {
            query: {
              radius_km: filters.radiusKm,
              hiring: filters.hiringOnly || undefined,
              capability: filters.capability || undefined,
              limit: 300,
            },
          },
        }),
      ),
    placeholderData: (previous) => previous, // keep pins while filters change
  });

  const items = startups.data?.items ?? [];
  const pins = useMemo(
    () => items.map((s) => ({ id: s.id, name: s.name, lat: s.location.lat, lng: s.location.lng, hiring: s.hiring })),
    [items],
  );
  const onSelect = useCallback((id: string) => setSelected(id), []);
  const chosen = items.find((s) => s.id === selected) ?? null;
  const center = startups.data?.center ?? { lat: 12.9716, lng: 77.5946 };
  const activeFilters = Number(filters.hiringOnly) + Number(!!filters.capability);

  return (
    // The map fills the screen between the top and the tab bar (sidebar on laptops).
    <div className="fixed inset-x-0 top-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] md:bottom-0 md:left-60">
      {startups.isError && !startups.data ? (
        <div className="p-4 pt-[max(1rem,env(safe-area-inset-top))]">
          <ErrorState error={startups.error} retry={startups.refetch} />
        </div>
      ) : noMap ? (
        <StartupList items={items} onSelect={onSelect} />
      ) : (
        <Suspense fallback={<div className="absolute inset-0 animate-pulse bg-surface" />}>
          <MapView
            center={center}
            zoom={ZOOM[filters.radiusKm] ?? 11}
            pins={pins}
            selectedId={selected}
            onSelect={onSelect}
            onUnavailable={() => setNoMap(true)}
            fitKey={`${JSON.stringify(filters)}:${startups.data ? items.length : "loading"}`}
          />
        </Suspense>
      )}

      {/* One line of context and one filter button, floating over the map. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-4 pt-[max(1rem,env(safe-area-inset-top))]">
        <div className="pointer-events-auto rounded-full border border-line bg-black/85 px-4 py-2.5 text-sm whitespace-nowrap backdrop-blur">
          {startups.isPending ? (
            "Finding startups…"
          ) : (
            <span>
              <span className="font-semibold">{startups.data?.total ?? 0}</span>
              {student ? ` within ${filters.radiusKm} km` : " startups"} ·{" "}
              <span className="text-green">{items.filter((s) => s.hiring).length} hiring</span>
            </span>
          )}
        </div>
        <button
          onClick={() => setFiltersOpen(true)}
          className="pointer-events-auto min-h-11 rounded-full border border-line bg-black/85 px-4 text-sm font-semibold backdrop-blur hover:border-muted"
        >
          Filters{activeFilters ? ` · ${activeFilters}` : ""}
        </button>
      </div>

      {startups.data && items.length === 0 && (
        <div className="absolute inset-x-4 bottom-4">
          <Empty>No startups match these filters. Try a wider distance.</Empty>
        </div>
      )}

      <Sheet open={filtersOpen} onClose={() => setFiltersOpen(false)} title="Filters">
        <FilterForm
          initial={filters}
          student={student}
          onApply={(f) => {
            setFilters(f);
            setFiltersOpen(false);
          }}
        />
      </Sheet>

      <Sheet open={chosen !== null} onClose={() => setSelected(null)} title={chosen?.name ?? ""}>
        {chosen && <StartupSheet startup={chosen} student={student} />}
      </Sheet>
    </div>
  );
}

function FilterForm({
  initial,
  student,
  onApply,
}: {
  initial: Filters;
  student: boolean;
  onApply: (f: Filters) => void;
}) {
  const [f, setF] = useState(initial);
  const caps = useCapabilities();
  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        onApply(f);
      }}
    >
      <label className="flex min-h-11 items-center justify-between gap-4">
        <span>Hiring now only</span>
        <input
          type="checkbox"
          checked={f.hiringOnly}
          onChange={(e) => setF({ ...f, hiringOnly: e.target.checked })}
          className="size-6 accent-[var(--blue)]"
        />
      </label>
      <label className="flex flex-col gap-2">
        <span>Needs this skill</span>
        <select
          value={f.capability}
          onChange={(e) => setF({ ...f, capability: e.target.value })}
          className="min-h-11 rounded-xl border border-line bg-raised px-3"
        >
          <option value="">Any skill</option>
          {(caps.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {student && (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2">Distance</legend>
          <div className="grid grid-cols-3 gap-2">
            {[5, 10, 20].map((km) => (
              <button
                type="button"
                key={km}
                aria-pressed={f.radiusKm === km}
                onClick={() => setF({ ...f, radiusKm: km })}
                className={`min-h-11 rounded-xl border text-sm font-medium ${
                  f.radiusKm === km ? "border-blue bg-blue/10 text-blue" : "border-line bg-raised"
                }`}
              >
                {km} km
              </button>
            ))}
          </div>
        </fieldset>
      )}
      <div className="flex gap-3">
        <SecondaryButton
          type="button"
          onClick={() => setF({ hiringOnly: false, capability: "", radiusKm: student ? 10 : 50 })}
        >
          Clear
        </SecondaryButton>
        <PrimaryButton type="submit" className="flex-1">
          Show startups
        </PrimaryButton>
      </div>
    </form>
  );
}

function StartupSheet({ startup, student }: { startup: Startup; student: boolean }) {
  const queryClient = useQueryClient();
  const interest = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/startups/{startup_id}/interest", { params: { path: { startup_id: startup.id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["map"] }),
  });
  const interested = startup.interested || interest.isSuccess;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <span>{startup.sector}</span>
        {startup.stage && <span>· {startup.stage}</span>}
        {startup.distance_km != null && <span>· {startup.distance_km.toFixed(1)} km away</span>}
        {startup.hiring ? <Pill tone="green">Hiring</Pill> : <Pill>Not hiring</Pill>}
      </div>

      {student && startup.match && (
        <div className="flex items-baseline gap-3 rounded-2xl border border-line bg-raised p-4">
          <span className="text-display font-semibold tabular-nums">{startup.match.score}%</span>
          <span className="text-sm text-muted">
            match to your skills
            {startup.match.best_role ? ` (best fit: ${startup.match.best_role.title})` : ""}
          </span>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <h3 className="text-sm text-muted">Open roles</h3>
        {startup.jobs.length === 0 ? (
          <p>No open roles right now.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {startup.jobs.map((j) => (
              <li key={j.id}>
                <Link
                  to={`/jobs/${j.id}`}
                  className="flex min-h-11 items-center justify-between gap-3 rounded-xl border border-line px-4 py-2 hover:border-muted"
                >
                  <span>{j.title}</span>
                  <span className="text-sm text-muted">{j.compensation ?? (j.paid ? "Paid" : "Unpaid")}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      {interest.isError && <ErrorState error={interest.error} />}
      <div className="flex flex-col gap-3 sm:flex-row-reverse">
        {student ? (
          interested ? (
            <span className="flex min-h-11 flex-1 items-center justify-center rounded-full border border-green/40 bg-green/10 font-semibold text-green">
              You're interested
            </span>
          ) : (
            <PrimaryButton className="flex-1" disabled={interest.isPending} onClick={() => interest.mutate()}>
              I'm interested
            </PrimaryButton>
          )
        ) : null}
        <Link
          to={`/startups/${startup.id}`}
          className="inline-flex min-h-11 flex-1 items-center justify-center rounded-full border border-line bg-raised px-5 font-semibold hover:border-muted"
        >
          View startup
        </Link>
      </div>
      {startup.interest_count > 0 && (
        <p className="text-center text-sm text-muted">
          {startup.interest_count} {startup.interest_count === 1 ? "person is" : "people are"} interested
        </p>
      )}
    </div>
  );
}

/** Shown when the device can't draw the map (no WebGL): the same startups as a list. */
function StartupList({ items, onSelect }: { items: Startup[]; onSelect: (id: string) => void }) {
  if (items.length === 0) return <Skeleton lines={5} />;
  return (
    <ul className="h-full overflow-y-auto px-4 pt-20 pb-4">
      {items.map((s) => (
        <li key={s.id}>
          <button
            onClick={() => onSelect(s.id)}
            className="flex min-h-14 w-full items-center justify-between border-b border-line text-left"
          >
            <span>{s.name}</span>
            <span className="text-sm text-muted">{s.hiring ? "Hiring" : ""}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
