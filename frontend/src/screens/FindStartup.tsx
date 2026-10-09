import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { api, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { Avatar, Badge, EmptyState, ErrorBlock, HiringBadge, Icon, List, ListRow, SkeletonRows } from "../components/ds";
import { Page, PageHeader } from "../components/Shell";

/** Startups in the city, searchable by name. Founders also use it to find their own
 *  startup (often already here from public data) and claim it. */
export default function FindStartup() {
  const { member } = useAuth();
  const founder = member?.role === "founder";
  const [text, setText] = useState("");
  const q = useDeferredValue(text.trim());
  const results = useQuery({
    queryKey: ["startups", "search", q],
    queryFn: () =>
      unwrap(api.GET("/api/startups", { params: { query: { ...(q.length >= 2 ? { q } : {}), limit: 20 } } })),
  });
  return (
    <Page>
      <PageHeader
        title={founder ? "Find your startup" : "Startups"}
        intro={
          founder
            ? "Many startups are already here from public data. Find yours to claim it."
            : "Startups in your city. Search by name or what they do."
        }
      />
      <label className="flex min-h-11 items-center gap-2 rounded-lg border border-line2 bg-panel px-3 focus-within:border-fg2">
        <Icon name="search" size={18} className="text-muted" />
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Startup name"
          aria-label="Startup name"
          className="min-h-11 flex-1 bg-transparent outline-none placeholder:text-muted"
        />
      </label>
      {results.isPending ? (
        <SkeletonRows rows={4} label="Loading startups" />
      ) : results.isError ? (
        <ErrorBlock error={results.error} retry={() => void results.refetch()} />
      ) : results.data.items.length === 0 ? (
        <EmptyState icon="building" title="No startup by that name yet">
          Check the spelling, or try a word from what they do.
        </EmptyState>
      ) : (
        <List label="Startups">
          {results.data.items.map((s) => (
            <ListRow
              key={s.id}
              to={`/startups/${s.id}`}
              leading={<Avatar name={s.name} kind="startup" />}
              title={s.name}
              meta={`${s.sector} · ${s.website_domain}`}
              trailing={
                founder ? (
                  s.claimed ? <Badge>Claimed</Badge> : <Badge tone="accent">Claim</Badge>
                ) : (
                  <HiringBadge hiring={s.hiring} />
                )
              }
            />
          ))}
        </List>
      )}
    </Page>
  );
}
