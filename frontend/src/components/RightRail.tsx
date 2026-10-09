import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { Avatar, Card, SkeletonBlock } from "./ds";
import { ProfileStrength } from "./ProfileStrength";

// The right rail on wide screens (≥1280px): profile strength, then people worth meeting
// or (students) jobs near you. On smaller screens Home shows profile strength instead.

function NearbyJobs() {
  const q = useQuery({
    queryKey: ["jobs", "rail"],
    queryFn: () => unwrap(api.GET("/api/jobs", { params: { query: { radius_km: 10, limit: 3 } } })),
  });
  return (
    <Card aria-label="Jobs near you">
      <h2 className="font-semibold">Jobs near you</h2>
      {q.isPending ? (
        <SkeletonBlock className="mt-3 h-24 w-full" />
      ) : q.isError || q.data.items.length === 0 ? (
        <p className="mt-2 text-sm text-fg2">No open jobs within 10 km right now.</p>
      ) : (
        <ul className="mt-2 flex flex-col">
          {q.data.items.map((j) => (
            <li key={j.id}>
              <Link to={`/jobs/${j.id}`} className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-raised/70">
                <Avatar name={j.startup.name} size={32} kind="startup" />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-sm font-semibold">{j.title}</span>
                  <span className="truncate text-xs text-muted">
                    {j.startup.name}
                    {j.distance_km != null && ` · ${j.distance_km.toFixed(1)} km`}
                  </span>
                </span>
                {j.match && <span className="num text-sm">{j.match.score}%</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function PeopleWorthMeeting() {
  const q = useQuery({ queryKey: ["matches", "top"], queryFn: () => unwrap(api.GET("/api/matches")) });
  const people = (q.data?.items ?? []).filter((m) => m.candidate_type === "member").slice(0, 3);
  return (
    <Card aria-label="People worth meeting">
      <h2 className="font-semibold">People worth meeting</h2>
      {q.isPending ? (
        <SkeletonBlock className="mt-3 h-24 w-full" />
      ) : people.length === 0 ? (
        <p className="mt-2 text-sm text-fg2">When we find people who fit what you need, they'll show up here.</p>
      ) : (
        <ul className="mt-2 flex flex-col">
          {people.map((p) => (
            <li key={p.candidate_id}>
              <Link to="/matches" className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-raised/70">
                <Avatar name={p.title} size={32} />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-sm font-semibold">{p.title}</span>
                  <span className="truncate text-xs text-muted">{p.subtitle}</span>
                </span>
                <span className="num text-sm">{p.score}%</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function RightRail() {
  const { member } = useAuth();
  if (!member) return null;
  return (
    <>
      <ProfileStrength />
      {member.role === "student" ? <NearbyJobs /> : member.role !== "partner_admin" && member.verification_level >= 2 ? <PeopleWorthMeeting /> : null}
    </>
  );
}
