import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { api, type Schemas, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { pay } from "../components/jobs";
import { Page } from "../components/Shell";
import { Sheet } from "../components/Sheet";
import {
  Card,
  ErrorState,
  Muted,
  Pill,
  PrimaryButton,
  SecondaryButton,
  Skeleton,
  Stat,
  Title,
} from "../components/ui";

export default function StartupPage() {
  const { startupId = "" } = useParams();
  const { member } = useAuth();
  const queryClient = useQueryClient();
  const [claiming, setClaiming] = useState(false);
  const path = { params: { path: { startup_id: startupId } } };

  const startup = useQuery({
    queryKey: ["startup", startupId],
    queryFn: () => unwrap(api.GET("/api/startups/{startup_id}", path)),
  });
  const stats = useQuery({
    queryKey: ["startup", startupId, "stats"],
    queryFn: () => unwrap(api.GET("/api/startups/{startup_id}/stats", path)),
  });
  const interest = useMutation({
    mutationFn: () => unwrap(api.POST("/api/startups/{startup_id}/interest", path)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["startup", startupId] });
      void queryClient.invalidateQueries({ queryKey: ["map"] });
    },
  });

  if (startup.isPending) return <Page><Skeleton lines={4} className="h-24" /></Page>;
  if (startup.isError) return <Page><ErrorState error={startup.error} retry={startup.refetch} /></Page>;
  const s = startup.data;
  const mine = s.claimed_by_member_id === member?.id;
  const student = member?.role === "student";
  const canClaim = !s.claimed && member?.role === "founder";

  return (
    <Page>
      <div className="flex items-start gap-4">
        <span
          aria-hidden="true"
          className="flex size-16 shrink-0 items-center justify-center rounded-xl border border-line bg-raised text-xl font-semibold"
        >
          {s.name[0]}
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <Title>{s.name}</Title>
          <Muted>{[s.sector, s.stage, s.address].filter(Boolean).join(" · ")}</Muted>
          <div className="flex flex-wrap gap-2 pt-1">
            {s.hiring && <Pill tone="green">Hiring</Pill>}
            {mine ? (
              <Pill tone="blue">You manage this page</Pill>
            ) : s.claimed ? (
              <Pill>On Circuit</Pill>
            ) : (
              <Pill>Not on Circuit yet</Pill>
            )}
          </div>
        </div>
      </div>

      {stats.data && (
        <div className="grid grid-cols-3 gap-3">
          <Stat value={stats.data.interested_students} label="Students interested" />
          <Stat value={stats.data.view_count} label="Profile views" />
          <Stat value={stats.data.applications_waiting} label="Applications" />
        </div>
      )}

      {canClaim && (
        <Card className="flex flex-col gap-4 border-line2">
          <p>
            Is this your startup?{" "}
            {stats.data && stats.data.interested_students > 0
              ? `${stats.data.interested_students} students are interested in ${s.name}. `
              : ""}
            Claim the page to see who, read applications and post jobs.
          </p>
          <PrimaryButton onClick={() => setClaiming(true)}>Claim this startup</PrimaryButton>
        </Card>
      )}

      {mine && (
        <Link
          to={`/startups/${s.id}/applicants`}
          className="inline-flex min-h-11 items-center justify-center rounded-lg bg-accent px-5 font-semibold text-ink active:scale-[0.97] transition-transform"
        >
          See applicants
        </Link>
      )}

      {student && (
        <div>
          {stats.data?.you_are_interested || interest.isSuccess ? (
            <Pill tone="green">You're interested</Pill>
          ) : (
            <PrimaryButton disabled={interest.isPending} onClick={() => interest.mutate()}>
              I'm interested
            </PrimaryButton>
          )}
          {interest.isError && <ErrorState error={interest.error} />}
        </div>
      )}

      {s.description && <p className="text-muted">{s.description}</p>}

      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold">Open roles</h2>
        {s.jobs.length === 0 ? (
          <p className="text-muted">No open roles right now.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {s.jobs.map((j) => (
              <li key={j.id}>
                <Link
                  to={`/jobs/${j.id}`}
                  className="flex min-h-14 items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 hover:border-muted"
                >
                  <span>{j.title}</span>
                  <span className="text-sm text-muted">{pay(j)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {s.team.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">Team</h2>
          <p className="text-muted">{s.team.map((m) => m.display_name).join(", ")}</p>
        </section>
      )}

      <Sheet open={claiming} onClose={() => setClaiming(false)} title={`Claim ${s.name}`}>
        <ClaimFlow
          startup={s}
          onClaimed={() => {
            setClaiming(false);
            void queryClient.invalidateQueries({ queryKey: ["startup", startupId] });
            void queryClient.invalidateQueries({ queryKey: ["members", "me"] });
          }}
        />
      </Sheet>
    </Page>
  );
}

/** F3: prove you work there with an email on the startup's own domain. */
function ClaimFlow({ startup, onClaimed }: { startup: Schemas["StartupOut"]; onClaimed: () => void }) {
  const path = { params: { path: { startup_id: startup.id } } };
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/api/startups/{startup_id}/claim", { ...path, body: { email } })),
  });
  const verify = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/startups/{startup_id}/claim/verify", {
          ...path,
          body: { claim_id: start.data!.claim_id, code },
        }),
      ),
    onSuccess: onClaimed,
  });

  if (!start.data) {
    return (
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          start.mutate();
        }}
      >
        <label className="flex flex-col gap-2">
          <span>Your work email at {startup.website_domain}</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={`you@${startup.website_domain}`}
            className="min-h-11 rounded-xl border border-line bg-raised px-3 placeholder:text-muted"
          />
        </label>
        {start.isError && <ErrorState error={start.error} />}
        <PrimaryButton type="submit" disabled={start.isPending}>
          Send me a code
        </PrimaryButton>
      </form>
    );
  }
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        verify.mutate();
      }}
    >
      <p>We sent a 6-digit code to your @{start.data.sent_to_domain} address.</p>
      {start.data.dev_code && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-line p-3 text-sm text-muted">
          <span>
            Demo: no email is sent. The code is <span className="font-semibold text-fg">{start.data.dev_code}</span>.
          </span>
          <SecondaryButton type="button" onClick={() => setCode(start.data.dev_code ?? "")}>
            Use it
          </SecondaryButton>
        </div>
      )}
      <label className="flex flex-col gap-2">
        <span>Code</span>
        <input
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          required
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          className="min-h-11 rounded-xl border border-line bg-raised px-3 text-xl tracking-[0.4em] tabular-nums"
        />
      </label>
      {verify.isError && <ErrorState error={verify.error} />}
      <PrimaryButton type="submit" disabled={verify.isPending || code.length !== 6}>
        Claim {startup.name}
      </PrimaryButton>
    </form>
  );
}
