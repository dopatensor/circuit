import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api, type Schemas, unwrap } from "../api/client";
import { useCapabilities } from "../api/hooks";
import { useAuth } from "../auth";
import {
  Avatar,
  ButtonLink,
  Card,
  EmptyState,
  ErrorBlock,
  Icon,
  List,
  Section,
  SkeletonBlock,
  SkeletonRows,
  VerificationBadge,
} from "../components/ds";
import { ProofItemSummary, RepoSummary, VerifiedChips, VerifiedLabel, dateLabel, githubSummary } from "../components/proof";
import { Page } from "../components/Shell";
import { ROLE_LABEL } from "../nav";

type Member = Schemas["MemberPublic"];
const LEVEL = { 1: "basic", 2: "solid", 3: "strong" } as Record<number, string>;

/** "Can this person do the work?" A profile leads with proof of work, then skills. */
export default function Profile() {
  const { memberId = "" } = useParams();
  const { member: me } = useAuth();
  const q = useQuery({
    queryKey: ["members", memberId],
    queryFn: () => unwrap(api.GET("/api/members/{member_id}", { params: { path: { member_id: memberId } } })),
  });
  if (q.isPending)
    return (
      <Page>
        <SkeletonBlock className="h-32 w-full rounded-xl" />
        <SkeletonRows rows={3} label="Loading profile" />
      </Page>
    );
  if (q.isError)
    return (
      <Page>
        <ErrorBlock error={q.error} retry={() => void q.refetch()} />
      </Page>
    );
  const m = q.data;
  const own = me?.id === m.id;
  return (
    <Page>
      <Header m={m} own={own} />
      {m.role === "student" ? (
        <>
          <ProofOfWork m={m} own={own} />
          <Skills m={m} />
        </>
      ) : (
        <NeedsAndOffers m={m} />
      )}
    </Page>
  );
}

function Header({ m, own }: { m: Member; own: boolean }) {
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <Avatar name={m.display_name} size={56} />
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-[-0.015em]">{m.display_name}</h1>
          <p className="text-sm text-muted">{[ROLE_LABEL[m.role], m.sector, m.city].filter(Boolean).join(" · ")}</p>
          {m.college && (
            <p className="flex items-center gap-1.5 text-sm text-fg2">
              <Icon name="school" size={14} /> {m.college}
            </p>
          )}
        </div>
      </div>
      {m.bio && <p className="text-fg2">{m.bio}</p>}
      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <VerificationBadge level={m.verification_level} />
        {own && (
          <span className="text-sm text-muted">
            This is how others see you.{" "}
            <Link to="/me" className="font-semibold text-fg underline underline-offset-2">
              Back to Me
            </Link>
          </span>
        )}
      </div>
    </Card>
  );
}

function ProofOfWork({ m, own }: { m: Member; own: boolean }) {
  const g = m.proof.github;
  const items = m.proof.items;
  if (!g && items.length === 0) {
    return (
      <Section title="Proof of work">
        <EmptyState
          icon="doc"
          title={own ? "Show something you've built" : "No proof of work yet"}
          action={own ? <ButtonLink to="/me/proof" variant="primary">Add proof of work</ButtonLink> : undefined}
        >
          {own ? "Connect GitHub, or add a portfolio link or a case study." : "Their skills are below."}
        </EmptyState>
      </Section>
    );
  }
  return (
    <Section title="Proof of work" action={own ? { label: "Edit", to: "/me/proof" } : undefined}>
      {g && (
        <Card className="flex flex-col gap-4" aria-label="GitHub">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <a href={g.profile_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 font-semibold underline-offset-2 hover:underline">
              <Icon name="github" size={18} /> {g.login}
            </a>
            <span className="text-xs text-muted">Updated {dateLabel(g.fetched_at)}</span>
          </div>
          <p className="text-sm text-fg2">{githubSummary(g)}</p>
          {g.verified_capabilities.length > 0 && (
            <div className="flex flex-col gap-2">
              <VerifiedLabel />
              <VerifiedChips items={g.verified_capabilities} />
            </div>
          )}
          {g.homepage_url && (
            <a href={g.homepage_url} target="_blank" rel="noreferrer" className="text-sm text-fg2 underline underline-offset-2">
              {g.homepage_url.replace(/^https?:\/\//, "")}
            </a>
          )}
        </Card>
      )}
      {g && g.featured_repos.length > 0 && (
        <List label="Featured repos">
          {g.featured_repos.map((r) => (
            <li key={r.id} className="px-4 py-3.5">
              <RepoSummary repo={r} />
            </li>
          ))}
        </List>
      )}
      {g && g.external_prs.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="font-semibold">Merged pull requests to other projects</h3>
          <ul className="flex flex-col gap-1 text-sm">
            {g.external_prs.slice(0, 5).map((p) => (
              <li key={`${p.repo}-${p.url}`}>
                {p.url ? (
                  <a href={p.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                    {p.repo}
                  </a>
                ) : (
                  p.repo
                )}
                <span className="text-muted"> · {dateLabel(p.merged_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {items.length > 0 && (
        <List label="Other work">
          {items.map((i) => (
            <li key={i.id} className="px-4 py-3.5">
              <ProofItemSummary item={i} own={own} />
            </li>
          ))}
        </List>
      )}
    </Section>
  );
}

function Skills({ m }: { m: Member }) {
  const caps = useCapabilities();
  const verified = new Set(m.proof.github?.verified_capabilities.map((v) => v.capability_id) ?? []);
  if (m.skills.length === 0) return null;
  return (
    <Section title="Skills">
      <ul aria-label="Skills" className="flex flex-wrap gap-2">
        {m.skills.map((s) => (
          <li key={s.capability_id}>
            <span className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-raised px-3 text-sm">
              {verified.has(s.capability_id) && (
                <span title="Verified by GitHub" className="inline-flex">
                  <Icon name="github" size={14} />
                  <span className="sr-only">Verified by GitHub:</span>
                </span>
              )}
              {caps.name(s.capability_id)}
              <span className="text-xs text-muted">{LEVEL[s.level]}</span>
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function NeedsAndOffers({ m }: { m: Member }) {
  const caps = useCapabilities();
  const block = (title: string, rows: { id: string; capability_id: string; text: string }[]) =>
    rows.length > 0 && (
      <Section title={title}>
        <List label={title}>
          {rows.map((r) => (
            <li key={r.id} className="flex flex-col gap-0.5 px-4 py-3.5">
              <span className="font-semibold">{caps.name(r.capability_id)}</span>
              {r.text && <span className="text-sm text-fg2">{r.text}</span>}
            </li>
          ))}
        </List>
      </Section>
    );
  return (
    <>
      {block("Can help with", m.offers)}
      {block("Looking for", m.needs)}
      {m.startups.length > 0 && (
        <Section title="Startups">
          <List label="Startups">
            {m.startups.map((s) => (
              <li key={s.startup_id}>
                <Link to={`/startups/${s.startup_id}`} className="flex items-center justify-between gap-3 px-4 py-3.5 hover:bg-raised/60">
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-sm text-muted">{s.title}</span>
                </Link>
              </li>
            ))}
          </List>
        </Section>
      )}
    </>
  );
}
