import type { Schemas } from "../api/client";
import { Avatar, BridgeBadge } from "./ui";

type Match = Schemas["MatchOut"];

/** One match: who, the one-line reason, the Bridge badge if it crosses sectors. */
export function MatchCard({ match, action }: { match: Match; action?: React.ReactNode }) {
  return (
    <article
      className={`flex flex-col gap-4 rounded-2xl border bg-surface p-5 ${
        match.is_bridge ? "border-green/40" : "border-line"
      }`}
    >
      <div className="flex items-start gap-3">
        {match.candidate_type === "member" ? (
          <Avatar name={match.title} />
        ) : (
          <span
            aria-hidden="true"
            className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-line bg-raised font-semibold"
          >
            {match.title[0]}
          </span>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <h2 className="truncate text-base font-semibold">{match.title}</h2>
          <p className="truncate text-sm text-muted">{match.subtitle}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end">
          <span className="text-xl font-semibold tabular-nums">{match.score}%</span>
          <span className="text-sm text-muted">match</span>
        </div>
      </div>
      <p className="text-base">{match.reason}</p>
      {(match.is_bridge || action) && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          {match.is_bridge ? <BridgeBadge /> : <span />}
          {action}
        </div>
      )}
    </article>
  );
}
