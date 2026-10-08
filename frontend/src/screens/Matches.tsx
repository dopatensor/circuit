import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation } from "react-router";
import { api, type Schemas, withMeta } from "../api/client";
import { useAuth } from "../auth";
import { IntroSheet } from "../components/IntroSheet";
import { MatchCard } from "../components/MatchCard";
import { Page } from "../components/Shell";
import {
  Empty,
  ErrorState,
  LastUpdated,
  Muted,
  SecondaryButton,
  Skeleton,
  Title,
} from "../components/ui";

type Match = Schemas["MatchOut"];

const actionLink =
  "inline-flex min-h-11 items-center justify-center rounded-full border border-line bg-raised px-5 font-semibold hover:border-muted";

export default function Matches() {
  const { member } = useAuth();
  const { state } = useLocation();
  const [intro, setIntro] = useState<{ id: string; name: string } | null>(null);
  const matches = useQuery({
    queryKey: ["matches"],
    queryFn: () => withMeta(api.GET("/api/matches", { params: { query: { limit: 20 } } })),
  });
  // Students' matches are jobs; intros are for founders, mentors and investors.
  const canIntro = member?.role !== "student";
  const editLabel = canIntro ? "Edit what you need and offer" : "Edit your skills";

  /** One action per card: an intro to the person (or the startup's founder), else a link. */
  function action(m: Match) {
    if (canIntro && m.intro_member_id) {
      const name = m.candidate_type === "startup" ? `${m.title}'s founder` : m.title;
      return (
        <SecondaryButton onClick={() => setIntro({ id: m.intro_member_id!, name })}>
          Ask for intro
        </SecondaryButton>
      );
    }
    if (m.candidate_type === "job") {
      return (
        <Link to={`/jobs/${m.candidate_id}`} className={actionLink}>
          View job
        </Link>
      );
    }
    if (m.candidate_type === "startup") {
      return (
        <Link to={`/startups/${m.candidate_id}`} className={actionLink}>
          View startup
        </Link>
      );
    }
    return null;
  }

  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Title>Matches</Title>
        <Muted>Ranked by what you need and what you can offer.</Muted>
        <LastUpdated servedAt={matches.data?.servedAt} />
        <Link to="/me/profile" className="text-sm font-semibold text-blue hover:underline">
          {editLabel}
        </Link>
      </div>
      {(state as { saved?: boolean } | null)?.saved && (
        <p role="status" className="text-sm text-green">
          Saved. Your matches are up to date.
        </p>
      )}
      {matches.isPending ? (
        <Skeleton lines={4} className="h-36" />
      ) : matches.isError ? (
        <ErrorState error={matches.error} retry={matches.refetch} />
      ) : matches.data.data.items.length === 0 ? (
        <Empty>
          No matches yet.{" "}
          <Link to="/me/profile" className="font-semibold text-blue hover:underline">
            {canIntro ? "Add what you need and offer" : "Add your skills"}
          </Link>{" "}
          to get matched.
        </Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {matches.data.data.items.map((m) => (
            <MatchCard key={`${m.candidate_type}-${m.candidate_id}`} match={m} action={action(m)} />
          ))}
        </div>
      )}
      <IntroSheet memberId={intro?.id ?? null} name={intro?.name ?? ""} onClose={() => setIntro(null)} />
    </Page>
  );
}
