import { type QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Role, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { DemoStories } from "../components/DemoStories";
import { Page } from "../components/Shell";
import { Sheet } from "../components/Sheet";
import {
  Avatar,
  Card,
  Eyebrow,
  PrimaryButton,
  SecondaryButton,
  Stat,
  UNLOCKS,
  VerificationBadge,
} from "../components/ui";
import { ROLE_LABEL } from "../nav";

type StatDef = { label: string; key: string; load: () => Promise<number> };

// Three numbers about you, by role. Each loads on its own; a failure shows "–".
function statsFor(role: Role, queryClient: QueryClient): StatDef[] {
  const matches: StatDef = {
    label: "Matches",
    key: "matches",
    load: async () => (await unwrap(api.GET("/api/matches"))).items.length,
  };
  if (role === "student") {
    return [
      matches,
      {
        label: "Applications",
        key: "applications",
        load: async () => (await unwrap(api.GET("/api/applications/me"))).length,
      },
      {
        label: "Jobs within 10 km",
        key: "jobs-nearby",
        load: async () =>
          (await unwrap(api.GET("/api/jobs", { params: { query: { radius_km: 10, limit: 1 } } })))
            .total,
      },
    ];
  }
  if (role === "partner_admin") {
    // One request shared by all three tiles.
    const stats = () =>
      queryClient.fetchQuery({
        queryKey: ["dashboard", "stats"],
        queryFn: () => unwrap(api.GET("/api/dashboard/stats")),
        staleTime: 60_000,
      });
    return [
      { label: "Members", key: "members", load: async () => (await stats()).members },
      { label: "Startups", key: "startups", load: async () => (await stats()).startups },
      { label: "Intros made", key: "intros", load: async () => (await stats()).intros_accepted },
    ];
  }
  return [
    matches,
    {
      label: "Intros",
      key: "intros",
      load: async () => {
        const inbox = await unwrap(api.GET("/api/intros/me"));
        return inbox.sent.length + inbox.received.length + inbox.to_forward.length;
      },
    },
    {
      label: "Circuits",
      key: "circuits",
      load: async () => (await unwrap(api.GET("/api/circuits/me"))).length,
    },
  ];
}

function StatTile({ def, memberId }: { def: StatDef; memberId: string }) {
  const q = useQuery({ queryKey: ["me-stat", memberId, def.key], queryFn: def.load, retry: false });
  if (q.isPending) return <div className="h-[6.25rem] animate-pulse rounded-2xl bg-surface" />;
  return <Stat value={q.isError ? "–" : q.data} label={def.label} />;
}

export default function Me() {
  const { member, isDemo, logout } = useAuth();
  const [switching, setSwitching] = useState(false);
  const queryClient = useQueryClient();
  if (!member) return null;
  const level = Math.max(0, Math.min(3, member.verification_level));

  return (
    <Page>
      <Card className="flex flex-col gap-5">
        <div className="flex items-center gap-4">
          <Avatar name={member.display_name} size="lg" />
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="text-xl font-semibold tracking-tight">{member.display_name}</h1>
            <p className="text-sm text-muted">
              {[ROLE_LABEL[member.role], member.sector, member.city].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
          <VerificationBadge level={member.verification_level} />
          <span className="text-sm text-muted">{UNLOCKS[level]}</span>
        </div>
      </Card>

      <div className="grid grid-cols-3 gap-3">
        {statsFor(member.role, queryClient).map((def) => (
          <StatTile key={def.key} def={def} memberId={member.id} />
        ))}
      </div>

      {isDemo && (
        <Card className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-col gap-1">
            <Eyebrow>Demo mode</Eyebrow>
            <p>Switch to another person from the five demo stories.</p>
          </div>
          <PrimaryButton onClick={() => setSwitching(true)} className="shrink-0">
            Switch person
          </PrimaryButton>
        </Card>
      )}

      <div>
        <SecondaryButton onClick={() => void logout()}>Sign out</SecondaryButton>
      </div>

      <Sheet open={switching} onClose={() => setSwitching(false)} title="Switch person">
        <DemoStories onSwitched={() => setSwitching(false)} />
      </Sheet>
    </Page>
  );
}
