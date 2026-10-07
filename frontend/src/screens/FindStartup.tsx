import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { Page } from "../components/Shell";
import { Empty, ErrorState, Muted, Pill, Skeleton, Title } from "../components/ui";

/** Founders find their startup (often already here, from public data) to claim it. */
export default function FindStartup() {
  const [q, setQ] = useState("");
  const results = useQuery({
    queryKey: ["startups", "search", q],
    queryFn: () => unwrap(api.GET("/api/startups", { params: { query: { q: q.trim(), limit: 20 } } })),
    enabled: q.trim().length >= 2,
  });
  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Title>Find your startup</Title>
        <Muted>Many startups are already here from public data. Find yours to claim it.</Muted>
      </div>
      <input
        type="search"
        autoFocus
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Startup name"
        aria-label="Startup name"
        className="min-h-11 rounded-full border border-line bg-surface px-4 placeholder:text-muted"
      />
      {q.trim().length < 2 ? (
        <Empty>Type at least two letters of your startup's name.</Empty>
      ) : results.isPending ? (
        <Skeleton lines={3} className="h-16" />
      ) : results.isError ? (
        <ErrorState error={results.error} retry={results.refetch} />
      ) : results.data.items.length === 0 ? (
        <Empty>No startup by that name yet.</Empty>
      ) : (
        <ul className="flex flex-col gap-2">
          {results.data.items.map((s) => (
            <li key={s.id}>
              <Link
                to={`/startups/${s.id}`}
                className="flex min-h-16 items-center justify-between gap-3 rounded-2xl border border-line bg-surface px-4 hover:border-muted"
              >
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-semibold">{s.name}</span>
                  <span className="truncate text-sm text-muted">{s.sector} · {s.website_domain}</span>
                </span>
                {s.claimed ? <Pill>Claimed</Pill> : <Pill tone="blue">Claim</Pill>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
