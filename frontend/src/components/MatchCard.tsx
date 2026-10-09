import type { Schemas } from "../api/client";
import { Avatar, BridgeBadge, Score } from "./ds";

type Match = Schemas["MatchOut"];

/** The name to show initials for: a job shows its startup (the subtitle starts with it). */
export function avatarName(m: Match) {
  return m.candidate_type === "job" ? m.subtitle.split(" · ")[0] : m.title;
}

/** One match: who, the one-line reason (joined to the score by the line motif), and the
 *  Bridge badge if it crosses sectors. */
export function MatchCard({ match, action }: { match: Match; action?: React.ReactNode }) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-line bg-panel p-5">
      <div className="flex items-start gap-3">
        <Avatar name={avatarName(match)} kind={match.candidate_type === "member" ? "person" : "startup"} />
        <div className="flex min-w-0 flex-1 flex-col">
          <h2 className="truncate text-base font-semibold">{match.title}</h2>
          <p className="truncate text-sm text-muted">{match.subtitle}</p>
        </div>
        <Score value={match.score} />
      </div>
      <p className={`border-l pl-3 text-fg2 ${match.is_bridge ? "border-signal" : "border-line2"}`}>{match.reason}</p>
      {(match.is_bridge || action) && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          {match.is_bridge ? <BridgeBadge /> : <span />}
          {action}
        </div>
      )}
    </article>
  );
}
