import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { api, unwrap, withMeta } from "../api/client";
import { useCapabilities, useMyProfile } from "../api/hooks";
import { useAuth } from "../auth";
import { JOB_TYPE, pay, StatusPill } from "../components/jobs";
import { Page } from "../components/Shell";
import { Sheet } from "../components/Sheet";
import {
  Card,
  ErrorState,
  LastUpdated,
  Muted,
  Pill,
  PrimaryButton,
  Skeleton,
  Title,
} from "../components/ui";

export default function JobPage() {
  const { jobId = "" } = useParams();
  const { member } = useAuth();
  const caps = useCapabilities();
  const queryClient = useQueryClient();
  const [applying, setApplying] = useState(false);

  const job = useQuery({
    queryKey: ["jobs", "detail", jobId],
    queryFn: () => withMeta(api.GET("/api/jobs/{job_id}", { params: { path: { job_id: jobId } } })),
  });
  const student = member?.role === "student";
  const isFounder = member?.role === "founder";
  const profile = useMyProfile(isFounder);
  const mine = useQuery({
    queryKey: ["applications", "me"],
    queryFn: () => withMeta(api.GET("/api/applications/me")),
    enabled: student,
  });

  if (job.isPending) return <Page><Skeleton lines={4} className="h-24" /></Page>;
  if (job.isError) return <Page><ErrorState error={job.error} retry={job.refetch} /></Page>;
  const j = job.data.data;
  const application = mine.data?.data.find((a) => a.job.id === j.id);
  const matched = new Set(j.match?.matched ?? []);
  const ownStartup = profile.data?.startups.some((s) => s.startup_id === j.startup.id) ?? false;

  return (
    <Page>
      <div className="flex flex-col gap-2">
        <Link to={`/startups/${j.startup.id}`} className="text-sm text-blue hover:underline">
          {j.startup.name}
        </Link>
        <Title>{j.title}</Title>
        <Muted>
          {[JOB_TYPE[j.type], pay(j), j.distance_km != null ? `${j.distance_km.toFixed(1)} km away` : null]
            .filter(Boolean)
            .join(" · ")}
        </Muted>
        <LastUpdated servedAt={job.data.servedAt} />
      </div>

      {j.match && (
        <Card className="flex items-baseline gap-3">
          <span className={`text-display font-semibold tabular-nums ${j.match.score >= 80 ? "text-green" : ""}`}>
            {j.match.score}%
          </span>
          <span className="text-muted">match to your skills, not your college</span>
        </Card>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold">Skills needed</h2>
        <ul className="flex flex-wrap gap-2">
          {j.capabilities.map((c) => (
            <li key={c.capability_id}>
              {matched.has(c.capability_id) ? (
                <Pill tone="green">✓ {caps.name(c.capability_id)}</Pill>
              ) : (
                <Pill>{caps.name(c.capability_id)}</Pill>
              )}
            </li>
          ))}
        </ul>
        {student && matched.size > 0 && (
          <p className="text-sm text-muted">Green means you have that skill.</p>
        )}
      </section>

      {j.description && (
        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">About the role</h2>
          <p className="whitespace-pre-line text-muted">{j.description}</p>
        </section>
      )}

      {!j.startup.claimed && (
        <p className="text-sm text-muted">
          {j.startup.name} isn't on Circuit yet. Applications are saved and shown to the
          founder when they join.
        </p>
      )}

      {ownStartup && (
        <Link to={`/startups/${j.startup.id}/applicants`} className="text-sm text-blue hover:underline">
          See applicants
        </Link>
      )}

      {/* The main action, fixed at the bottom within thumb reach. */}
      {student && j.status === "open" && (
        <div className="sticky bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-10 md:bottom-6">
          {application || j.has_applied ? (
            <div className="flex min-h-14 items-center justify-between gap-3 rounded-2xl border border-line bg-surface px-5">
              <span>You applied</span>
              {application && <StatusPill status={application.status} />}
            </div>
          ) : (
            <PrimaryButton className="min-h-14 w-full" onClick={() => setApplying(true)}>
              Apply
            </PrimaryButton>
          )}
        </div>
      )}
      {j.status === "closed" && <Pill>This job is closed</Pill>}

      <Sheet open={applying} onClose={() => setApplying(false)} title={`Apply: ${j.title}`}>
        <ApplyForm
          jobId={j.id}
          onDone={() => {
            setApplying(false);
            void queryClient.invalidateQueries({ queryKey: ["applications"] });
            void queryClient.invalidateQueries({ queryKey: ["jobs"] });
          }}
        />
      </Sheet>
    </Page>
  );
}

function ApplyForm({ jobId, onDone }: { jobId: string; onDone: () => void }) {
  const [note, setNote] = useState("");
  const apply = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/jobs/{job_id}/apply", { params: { path: { job_id: jobId } }, body: { note } })),
    onSuccess: onDone,
  });
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        apply.mutate();
      }}
    >
      <label className="flex flex-col gap-2">
        <span>A short note to the founder (optional)</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          rows={4}
          placeholder="What you've built that fits this role."
          className="rounded-xl border border-line bg-raised p-3 placeholder:text-muted"
        />
        <span className="text-right text-sm text-muted">{note.length}/500</span>
      </label>
      {apply.isError && <ErrorState error={apply.error} />}
      <PrimaryButton type="submit" disabled={apply.isPending} className="min-h-14">
        {apply.isPending ? "Sending…" : "Send application"}
      </PrimaryButton>
    </form>
  );
}
