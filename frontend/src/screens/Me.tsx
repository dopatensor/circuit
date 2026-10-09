import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, type Role, unwrap } from "../api/client";
import { useMyProfile } from "../api/hooks";
import { useAuth } from "../auth";
import { DemoStories } from "../components/DemoStories";
import { Page } from "../components/Shell";
import { Sheet } from "../components/Sheet";
import { ThemePicker } from "../components/ThemePicker";
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
import { ButtonLink, SkeletonBlock } from "../components/ds";

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
  if (q.isPending) return <SkeletonBlock className="h-[6.25rem] w-full rounded-xl" />;
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
            <h1 className="text-xl font-semibold tracking-[-0.01em]">{member.display_name}</h1>
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

      {member.role !== "partner_admin" && (
        <Card className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-col gap-1">
            <Eyebrow>{member.role === "student" ? "Your skills" : "What you need and offer"}</Eyebrow>
            <p>
              {member.role === "student"
                ? "Jobs are matched to your skills, not your college."
                : "Your matches and circuits come from this."}
            </p>
          </div>
          <ButtonLink to="/me/profile" className="shrink-0">
            Edit
          </ButtonLink>
        </Card>
      )}

      {member.role === "student" && <ProofCard />}

      {member.role === "founder" && <YourStartups />}

      {member.role !== "partner_admin" && <Privacy memberId={member.id} student={member.role === "student"} />}

      <Card>
        <ThemePicker />
      </Card>

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

/** Students: proof of work at a glance, and the way to manage it. */
function ProofCard() {
  const profile = useMyProfile();
  const proof = profile.data?.proof;
  const summary = !proof
    ? null
    : [
        proof.github ? `GitHub: ${proof.github.login}` : "GitHub not connected",
        `${proof.items.length} other ${proof.items.length === 1 ? "item" : "items"}`,
      ].join(" · ");
  return (
    <Card className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div className="flex flex-col gap-1">
        <Eyebrow>Proof of work</Eyebrow>
        {profile.isPending ? <SkeletonBlock className="h-5 w-48" /> : <p>{summary ?? "Show what you've built."}</p>}
      </div>
      <ButtonLink to="/me/proof" className="shrink-0">
        Manage
      </ButtonLink>
    </Card>
  );
}

/** What others see: your public profile, and (students) whether your college shows. */
function Privacy({ memberId, student }: { memberId: string; student: boolean }) {
  const profile = useMyProfile();
  const queryClient = useQueryClient();
  const toggle = useMutation({
    mutationFn: (show: boolean) => unwrap(api.PATCH("/api/members/me", { body: { show_college: show } })),
    onSuccess: (me) => queryClient.setQueryData(["members", "me"], me),
  });
  const show = toggle.isPending ? toggle.variables : (profile.data?.show_college ?? true);
  return (
    <Card className="flex flex-col gap-4">
      <Eyebrow>Privacy</Eyebrow>
      {student && (
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 size-5 shrink-0 accent-[var(--accent)]"
            checked={show}
            disabled={profile.isPending || toggle.isPending}
            onChange={(e) => toggle.mutate(e.target.checked)}
          />
          <span className="flex flex-col gap-0.5">
            <span className="font-semibold">Show my college on my profile</span>
            <span className="text-sm text-muted">Founders' applicant lists never show it either way: they rank on skills and proof of work.</span>
          </span>
        </label>
      )}
      {toggle.isError && <p role="alert" className="text-sm text-danger">Couldn't save that. Try again.</p>}
      <Link to={`/people/${memberId}`} className="self-start text-sm font-semibold text-fg underline underline-offset-2 hover:text-fg2">
        See your profile as others see it
      </Link>
    </Card>
  );
}

/** Founders: the startups you're part of, and a way to find and claim yours. */
function YourStartups() {
  const profile = useMyProfile();
  const startups = profile.data?.startups ?? [];
  return (
    <Card className="flex flex-col gap-4">
      <Eyebrow>Your startups</Eyebrow>
      {profile.isPending ? (
        <SkeletonBlock className="h-14 w-full rounded-lg" />
      ) : startups.length === 0 ? (
        <p className="text-muted">You haven't claimed a startup yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {startups.map((s) => (
            <li key={s.startup_id}>
              <Link
                to={`/startups/${s.startup_id}`}
                className="flex min-h-14 items-center justify-between gap-3 rounded-lg border border-line bg-raised px-4 hover:border-line2"
              >
                <span className="font-semibold">{s.name}</span>
                <span className="text-sm text-muted">{s.title}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link to="/startups" className="text-sm font-semibold text-fg underline underline-offset-2 hover:text-fg2">
        Find and claim your startup
      </Link>
    </Card>
  );
}
