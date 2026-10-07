import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api, type Schemas, withMeta } from "../api/client";
import { useCapabilities } from "../api/hooks";
import { JOB_TYPE, pay, StatusPill } from "../components/jobs";
import { Page } from "../components/Shell";
import { Sheet } from "../components/Sheet";
import {
  Empty,
  ErrorState,
  LastUpdated,
  PrimaryButton,
  SecondaryButton,
  Skeleton,
  Title,
} from "../components/ui";

type JobType = Schemas["JobOut"]["type"];
type Filters = { type: JobType | ""; paid: "" | "paid" | "unpaid"; capability: string; radiusKm: number };
const NO_FILTERS: Filters = { type: "", paid: "", capability: "", radiusKm: 10 };

export default function Jobs() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "applications" ? "applications" : "open";
  return (
    <Page>
      <Title>Jobs</Title>
      <div role="tablist" className="grid grid-cols-2 rounded-full border border-line bg-surface p-1">
        {(
          [
            ["open", "Open jobs"],
            ["applications", "My applications"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setParams(key === "open" ? {} : { tab: key }, { replace: true })}
            className={`min-h-11 rounded-full text-sm font-semibold transition-colors ${
              tab === key ? "bg-raised text-fg" : "text-muted hover:text-fg"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "open" ? <OpenJobs /> : <MyApplications />}
    </Page>
  );
}

function OpenJobs() {
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [open, setOpen] = useState(false);
  const jobs = useQuery({
    queryKey: ["jobs", search, filters],
    queryFn: () =>
      withMeta(
        api.GET("/api/jobs", {
          params: {
            query: {
              q: search.trim() || undefined,
              type: filters.type || undefined,
              paid: filters.paid ? filters.paid === "paid" : undefined,
              capability: filters.capability || undefined,
              radius_km: filters.radiusKm,
              limit: 50,
            },
          },
        }),
      ),
    placeholderData: (previous) => previous,
  });
  const active =
    Number(!!filters.type) + Number(!!filters.paid) + Number(!!filters.capability) +
    Number(filters.radiusKm !== NO_FILTERS.radiusKm);

  return (
    <>
      <div className="flex gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search roles, e.g. backend"
          aria-label="Search jobs"
          className="min-h-11 min-w-0 flex-1 rounded-full border border-line bg-surface px-4 placeholder:text-muted"
        />
        <SecondaryButton onClick={() => setOpen(true)}>
          Filters{active ? ` · ${active}` : ""}
        </SecondaryButton>
      </div>
      <LastUpdated servedAt={jobs.data?.servedAt} />
      {jobs.isPending ? (
        <Skeleton lines={5} className="h-20" />
      ) : jobs.isError && !jobs.data ? (
        <ErrorState error={jobs.error} retry={jobs.refetch} />
      ) : jobs.data.data.items.length === 0 ? (
        <Empty>No jobs match. Try another search or a wider distance.</Empty>
      ) : (
        <ul className="flex flex-col gap-2">
          {jobs.data.data.items.map((j) => (
            <li key={j.id}>
              <Link
                to={`/jobs/${j.id}`}
                className="flex items-center gap-4 rounded-2xl border border-line bg-surface p-4 transition-colors hover:border-muted"
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-semibold">{j.title}</span>
                  <span className="truncate text-sm text-muted">
                    {j.startup.name}
                    {j.distance_km != null ? ` · ${j.distance_km.toFixed(1)} km` : ""} · {JOB_TYPE[j.type]}
                  </span>
                </span>
                {j.match && (
                  <span className="flex shrink-0 flex-col items-end">
                    <span
                      className={`text-xl font-semibold tabular-nums ${j.match.score >= 80 ? "text-green" : ""}`}
                    >
                      {j.match.score}%
                    </span>
                    <span className="text-sm text-muted">match</span>
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Sheet open={open} onClose={() => setOpen(false)} title="Filters">
        <JobFilters
          initial={filters}
          onApply={(f) => {
            setFilters(f);
            setOpen(false);
          }}
        />
      </Sheet>
    </>
  );
}

function Choice<T extends string | number>({
  legend,
  value,
  options,
  onChange,
}: {
  legend: string;
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2">{legend}</legend>
      <div className="grid grid-cols-3 gap-2">
        {options.map(([v, label]) => (
          <button
            type="button"
            key={String(v)}
            aria-pressed={value === v}
            onClick={() => onChange(v)}
            className={`min-h-11 rounded-xl border px-2 text-sm font-medium ${
              value === v ? "border-blue bg-blue/10 text-blue" : "border-line bg-raised"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function JobFilters({ initial, onApply }: { initial: Filters; onApply: (f: Filters) => void }) {
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
      <Choice
        legend="Type"
        value={f.type}
        options={[["", "Any"], ["internship", "Internship"], ["full_time", "Full-time"]]}
        onChange={(type) => setF({ ...f, type })}
      />
      <Choice
        legend="Pay"
        value={f.paid}
        options={[["", "Any"], ["paid", "Paid"], ["unpaid", "Unpaid"]]}
        onChange={(paid) => setF({ ...f, paid })}
      />
      <Choice
        legend="Distance"
        value={f.radiusKm}
        options={[[5, "5 km"], [10, "10 km"], [25, "25 km"]]}
        onChange={(radiusKm) => setF({ ...f, radiusKm })}
      />
      <label className="flex flex-col gap-2">
        <span>Uses this skill</span>
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
      <div className="flex gap-3">
        <SecondaryButton type="button" onClick={() => setF(NO_FILTERS)}>
          Clear
        </SecondaryButton>
        <PrimaryButton type="submit" className="flex-1">
          Show jobs
        </PrimaryButton>
      </div>
    </form>
  );
}

function MyApplications() {
  const apps = useQuery({
    queryKey: ["applications", "me"],
    queryFn: () => withMeta(api.GET("/api/applications/me")),
  });
  if (apps.isPending) return <Skeleton lines={3} className="h-20" />;
  if (apps.isError) return <ErrorState error={apps.error} retry={apps.refetch} />;
  if (apps.data.data.length === 0)
    return <Empty>You haven't applied to anything yet. Open a job to apply.</Empty>;
  return (
    <>
      <LastUpdated servedAt={apps.data.servedAt} />
      <ul className="flex flex-col gap-2">
        {apps.data.data.map((a) => (
          <li key={a.id}>
            <Link
              to={`/jobs/${a.job.id}`}
              className="flex items-center gap-4 rounded-2xl border border-line bg-surface p-4 hover:border-muted"
            >
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-semibold">{a.job.title}</span>
                <span className="truncate text-sm text-muted">
                  {a.job.startup_name} · {pay(a.job)}
                </span>
              </span>
              <StatusPill status={a.status} />
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
