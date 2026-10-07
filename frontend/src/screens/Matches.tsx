import { useQuery } from "@tanstack/react-query";
import { api, withMeta } from "../api/client";
import { MatchCard } from "../components/MatchCard";
import { Page } from "../components/Shell";
import { Empty, ErrorState, LastUpdated, Muted, Skeleton, Title } from "../components/ui";

export default function Matches() {
  const matches = useQuery({
    queryKey: ["matches"],
    queryFn: () => withMeta(api.GET("/api/matches", { params: { query: { limit: 20 } } })),
  });

  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Title>Matches</Title>
        <Muted>Ranked by what you need and what you can offer.</Muted>
        <LastUpdated servedAt={matches.data?.servedAt} />
      </div>
      {matches.isPending ? (
        <Skeleton lines={4} className="h-36" />
      ) : matches.isError ? (
        <ErrorState error={matches.error} retry={matches.refetch} />
      ) : matches.data.data.items.length === 0 ? (
        <Empty>No matches yet. Add what you need and what you offer to get matched.</Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {matches.data.data.items.map((m) => (
            <MatchCard key={`${m.candidate_type}-${m.candidate_id}`} match={m} />
          ))}
        </div>
      )}
    </Page>
  );
}
