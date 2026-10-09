import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api, type Schemas, unwrap } from "../api/client";
import { useMyProfile } from "../api/hooks";
import { useAuth } from "../auth";
import {
  Avatar,
  BridgeBadge,
  ButtonLink,
  Card,
  EmptyState,
  ErrorBlock,
  List,
  ListRow,
  Score,
  Section,
  SkeletonBlock,
  SkeletonRows,
  Stepper,
} from "../components/ds";
import { avatarName } from "../components/MatchCard";
import { ProfileStrength, strengthItems } from "../components/ProfileStrength";
import { Page, PageHeader } from "../components/Shell";

// Home: "What should I do this week?" The one thing is the next-step card; below it,
// the best matches (or, for partner admins, intros to pass on). R4 replaces the lists
// with the opportunities feed; the structure stays the same.

type Step = {
  /** The match featured in the card (left out of the list below). */
  featured?: string;
  path?: { steps: string[]; current: number; label: string };
  title: string;
  text: ReactNode;
  action: { to: string; label: string };
  secondary?: { to: string; label: string };
};

function greeting(name: string) {
  const h = new Date().getHours();
  const part = h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
  const first = name.replace(/^(Dr|Mr|Ms|Mrs|Prof)\.?\s+/i, "").split(/\s+/)[0];
  return `Good ${part}, ${first}`;
}

function useNextStep(role: Schemas["MemberSummary"]["role"]): { data?: Step; isPending: boolean; error?: unknown; retry: () => void } {
  const me = useMyProfile();
  const student = role === "student";
  const partner = role === "partner_admin";
  const matches = useQuery({
    queryKey: ["matches", "top"],
    queryFn: () => unwrap(api.GET("/api/matches")),
    enabled: !partner && (me.data?.verification_level ?? 0) >= 2,
  });
  const applications = useQuery({
    queryKey: ["applications", "me", "home"],
    queryFn: () => unwrap(api.GET("/api/applications/me")),
    enabled: student,
  });
  const intros = useQuery({
    queryKey: ["intros", "me", "home"],
    queryFn: () => unwrap(api.GET("/api/intros/me")),
    enabled: !student,
  });
  const circuits = useQuery({
    queryKey: ["circuits", "me", "home"],
    queryFn: () => unwrap(api.GET("/api/circuits/me")),
    enabled: !student && !partner,
  });

  const retry = () => {
    void me.refetch();
    void matches.refetch();
  };
  if (me.isError) return { isPending: false, error: me.error, retry };
  if (me.isPending) return { isPending: true, retry };
  const profile = me.data;
  const profileDone = strengthItems(profile).slice(0, 2).every((i) => i.done);

  if (student) {
    if (applications.isPending || (matches.isPending && matches.fetchStatus !== "idle")) return { isPending: true, retry };
    const path = (current: number) => ({
      steps: ["Profile", "Proof", "Apply", "Interview"],
      current,
      label: "Your path to an internship",
    });
    if (!profileDone) {
      return {
        isPending: false,
        retry,
        data: {
          path: path(0),
          title: "Finish your profile",
          text: "Add your skills and a short bio. Founders match on what you can do, not your college.",
          action: { to: "/me/profile", label: "Add your skills" },
        },
      };
    }
    const apps = (applications.data ?? []).filter((a) => a.status !== "withdrawn");
    const shortlisted = apps.find((a) => a.status === "shortlisted" || a.status === "hired");
    if (shortlisted) {
      return {
        isPending: false,
        retry,
        data: {
          path: path(3),
          title: `${shortlisted.job.startup_name} ${shortlisted.status === "hired" ? "hired you" : "shortlisted you"}`,
          text: `For ${shortlisted.job.title}. Keep an eye on your inbox; they'll get in touch about next steps.`,
          action: { to: "/jobs?tab=applications", label: "See your applications" },
        },
      };
    }
    const topJob = matches.data?.items.find((m) => m.candidate_type === "job");
    const hasProof = profile.proof.github !== null || profile.proof.items.length > 0;
    if (!hasProof && apps.length === 0) {
      return {
        isPending: false,
        retry,
        data: {
          path: path(1),
          title: "Show something you've built",
          text: "Connect GitHub, or add a portfolio link or a case study. Founders see it next to your skills.",
          action: { to: "/me/proof", label: "Add proof of work" },
          secondary: topJob ? { to: `/jobs/${topJob.candidate_id}`, label: "Skip: see your top job" } : { to: "/jobs", label: "Browse jobs" },
        },
      };
    }
    if (apps.length === 0 && topJob) {
      return {
        isPending: false,
        retry,
        data: {
          path: path(2),
          title: `Apply to ${topJob.title} at ${topJob.subtitle.split(" · ")[0]}`,
          text: topJob.reason,
          action: { to: `/jobs/${topJob.candidate_id}`, label: "See the job" },
          featured: topJob.candidate_id,
          secondary: { to: "/jobs", label: "Browse all jobs" },
        },
      };
    }
    return {
      isPending: false,
      retry,
      data: {
        path: path(apps.length ? 3 : 2),
        title: apps.length ? `You've applied to ${apps.length} ${apps.length === 1 ? "job" : "jobs"}` : "Find a job to apply to",
        text: apps.length
          ? "Founders usually reply within a week. Meanwhile, one more good application helps."
          : "Browse jobs near you; each one shows how well your skills fit.",
        action: apps.length ? { to: "/jobs?tab=applications", label: "See your applications" } : { to: "/jobs", label: "Browse jobs" },
        secondary: apps.length ? { to: "/jobs", label: "Browse jobs" } : undefined,
      },
    };
  }

  if (intros.isPending || (circuits.isPending && circuits.fetchStatus !== "idle")) return { isPending: true, retry };
  const inbox = intros.data;
  const waiting = inbox
    ? [...inbox.to_forward, ...inbox.received].filter((i) => i.actions.some((a) => a === "forward" || a === "accept"))
    : [];

  if (partner) {
    return {
      isPending: false,
      retry,
      data: waiting.length
        ? {
            title: `Pass on ${waiting.length} intro ${waiting.length === 1 ? "request" : "requests"}`,
            text: "People are asking you to introduce them. A quick yes or no keeps things moving.",
            action: { to: "/inbox", label: "Open your inbox" },
            secondary: { to: "/dashboard", label: "See ecosystem gaps" },
          }
        : {
            title: "See where your ecosystem is short of help",
            text: "Which skills founders need that nobody nearby offers, by area.",
            action: { to: "/dashboard", label: "Open the gaps" },
          },
    };
  }

  const founder = role === "founder";
  const path = (current: number) => ({
    steps: ["Profile", "Matches", "Intros"],
    current,
    label: founder ? "Your path to the right people" : "Your path to helping founders",
  });
  const circuit = (circuits.data ?? []).find((c) => c.actions.includes("accept"));
  if (circuit) {
    return {
      isPending: false,
      retry,
      data: {
        title: "You've been offered an exchange circuit",
        text: circuit.sentence,
        action: { to: "/circuits", label: "See the circuit" },
      },
    };
  }
  if (waiting.length) {
    return {
      isPending: false,
      retry,
      data: {
        path: path(2),
        title: `Answer ${waiting.length} intro ${waiting.length === 1 ? "request" : "requests"}`,
        text: "Someone asked to be introduced. Answer within a few days so the intro stays warm.",
        action: { to: "/inbox", label: "Open your inbox" },
      },
    };
  }
  if (!profileDone) {
    return {
      isPending: false,
      retry,
      data: {
        path: path(0),
        title: founder ? "Say what you need and what you offer" : "Say what you can offer",
        text: "We match people on needs and offers, across sectors. Two minutes, and your matches get much better.",
        action: { to: "/me/profile", label: "Update your profile" },
      },
    };
  }
  const top = matches.data?.items.find((m) => m.intro_member_id);
  const sent = inbox?.sent.length ?? 0;
  return {
    isPending: false,
    retry,
    data: {
      path: path(sent ? 3 : 1),
      title: top ? `Meet ${top.title}` : "Look through your matches",
      text: top ? top.reason : "People and startups who need what you offer, and offer what you need.",
      action: { to: "/matches", label: top ? "See why, and ask for an intro" : "See your matches" },
      featured: top?.candidate_id,
    },
  };
}

function NextStep({ step }: { step: ReturnType<typeof useNextStep> }) {
  if (step.error) return <ErrorBlock error={step.error} retry={step.retry} />;
  if (step.isPending || !step.data) return <SkeletonBlock className="h-56 w-full rounded-xl" />;
  const s = step.data;
  return (
    <Card aria-label="Your next step" className="flex flex-col gap-5">
      {s.path && (
        <>
          <p className="text-xs font-semibold tracking-[0.06em] text-muted uppercase">{s.path.label}</p>
          <Stepper steps={s.path.steps} current={s.path.current} label={s.path.label} />
        </>
      )}
      <div>
        <h2 className="text-lg font-semibold">{s.title}</h2>
        <p className="mt-1 text-sm text-fg2">{s.text}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <ButtonLink to={s.action.to} variant="primary">
          {s.action.label}
        </ButtonLink>
        {s.secondary && (
          <ButtonLink to={s.secondary.to} variant="ghost">
            {s.secondary.label}
          </ButtonLink>
        )}
      </div>
    </Card>
  );
}

function TopMatches({ level, featured }: { level: number; featured?: string }) {
  const q = useQuery({ queryKey: ["matches", "top"], queryFn: () => unwrap(api.GET("/api/matches")), enabled: level >= 2 });
  const items = (q.data?.items ?? []).filter((m) => m.candidate_id !== featured).slice(0, 3);
  return (
    <Section title="Matches for you" action={items.length ? { label: "See all", to: "/matches" } : undefined}>
      {level < 2 ? (
        <EmptyState icon="lock" title="Verify your work email to see matches">
          Matches need verification level 2, so people know who they're talking to.
        </EmptyState>
      ) : q.isPending ? (
        <SkeletonRows rows={3} label="Loading matches" />
      ) : q.isError ? (
        <ErrorBlock error={q.error} retry={() => void q.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState icon="people" title="No matches yet" action={<ButtonLink to="/me/profile" size="sm">Update your profile</ButtonLink>}>
          Add what you need and what you can offer, and we'll look again.
        </EmptyState>
      ) : (
        <List label="Matches for you">
          {items.map((m) => (
            <ListRow
              key={`${m.candidate_type}-${m.candidate_id}`}
              to={m.candidate_type === "job" ? `/jobs/${m.candidate_id}` : m.candidate_type === "startup" ? `/startups/${m.candidate_id}` : "/matches"}
              leading={<Avatar name={avatarName(m)} kind={m.candidate_type === "member" ? "person" : "startup"} />}
              title={m.title}
              meta={m.subtitle}
              why={
                <span className="flex flex-col items-start gap-1.5">
                  {m.reason}
                  {m.is_bridge && <BridgeBadge />}
                </span>
              }
              trailing={<Score value={m.score} />}
            />
          ))}
        </List>
      )}
    </Section>
  );
}

function IntrosToPassOn() {
  const q = useQuery({ queryKey: ["intros", "me", "home"], queryFn: () => unwrap(api.GET("/api/intros/me")) });
  const items = (q.data?.to_forward ?? []).filter((i) => i.actions.includes("forward")).slice(0, 3);
  return (
    <Section title="Intros to pass on" action={{ label: "Open inbox", to: "/inbox" }}>
      {q.isPending ? (
        <SkeletonRows rows={2} />
      ) : q.isError ? (
        <ErrorBlock error={q.error} retry={() => void q.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState icon="inbox" title="Nothing to pass on">
          When someone asks you to introduce them, the request shows up here.
        </EmptyState>
      ) : (
        <List label="Intros to pass on">
          {items.map((i) => (
            <ListRow
              key={i.id}
              to="/inbox"
              leading={<Avatar name={i.sender.display_name} />}
              title={`${i.sender.display_name} → ${i.target.display_name}`}
              why={i.reason}
            />
          ))}
        </List>
      )}
    </Section>
  );
}

export default function Home() {
  const { member } = useAuth();
  if (!member) return null;
  return <HomeFor member={member} />;
}

function HomeFor({ member }: { member: Schemas["MemberSummary"] }) {
  const step = useNextStep(member.role);
  const intro = member.role === "partner_admin" ? "Here's what needs you this week." : "Here's what to do this week.";
  return (
    <Page>
      <PageHeader title={greeting(member.display_name)} intro={intro} />
      <NextStep step={step} />
      {member.role === "partner_admin" ? (
        <IntrosToPassOn />
      ) : (
        <TopMatches level={member.verification_level} featured={step.data?.featured} />
      )}
      {/* The right rail holds this on wide screens; here only while there's a step left. */}
      <div className="xl:hidden">
        <ProfileStrength hideWhenDone />
      </div>
    </Page>
  );
}
