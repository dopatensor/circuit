import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { useCapabilities, useMyProfile } from "../api/hooks";
import { ChipPicker } from "../components/Chips";
import { Button, ButtonLink, EmptyState, ErrorBlock, SkeletonBlock, useToast } from "../components/ds";
import { Page, PageHeader } from "../components/Shell";

type JobType = "internship" | "full_time" | "part_time" | "contract";
const TYPES: [JobType, string][] = [
  ["internship", "Internship"],
  ["full_time", "Full-time"],
  ["part_time", "Part-time"],
  ["contract", "Contract"],
];

const field = "min-h-11 w-full rounded-lg border border-line2 bg-panel px-3 py-2 outline-none placeholder:text-muted focus:border-fg2";

/** Founders post a job for a startup they've claimed. Students then see it on the map,
 *  in Jobs and in their matches (scored on the skills picked here). */
export default function PostJob() {
  const me = useMyProfile();
  const caps = useCapabilities();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [startupId, setStartupId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [type, setType] = useState<JobType>("internship");
  const [paid, setPaid] = useState(true);
  const [pay, setPay] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState<string[]>([]);

  // Jobs belong to a startup you claimed (being on its team isn't enough).
  const startups = (me.data?.startups ?? []).filter((s) => s.is_claimer);
  const chosen = startupId ?? startups[0]?.startup_id ?? null;

  const post = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/startups/{startup_id}/jobs", {
          params: { path: { startup_id: chosen! } },
          body: {
            title: title.trim(),
            type,
            paid,
            compensation: paid && pay.trim() ? pay.trim() : null,
            description: description.trim(),
            capabilities: skills.map((id) => ({ capability_id: id, min_level: 2 })),
          },
        }),
      ),
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      toast({ message: "Job posted. Students nearby can see it now." });
      navigate(`/jobs/${job.id}`);
    },
  });

  if (me.isPending || caps.isPending)
    return (
      <Page>
        <SkeletonBlock className="h-9 w-1/2" />
        <SkeletonBlock className="h-80 w-full rounded-xl" />
      </Page>
    );
  if (me.isError) return <Page><ErrorBlock error={me.error} retry={() => void me.refetch()} /></Page>;
  if (caps.isError) return <Page><ErrorBlock error={caps.error} retry={() => void caps.refetch()} /></Page>;

  if (startups.length === 0)
    return (
      <Page>
        <PageHeader title="Post a job" />
        <EmptyState
          icon="building"
          title="Claim your startup first"
          action={<ButtonLink to="/startups" variant="primary">Find your startup</ButtonLink>}
        >
          Jobs belong to a startup page. Find yours (it may already be here) and claim it with your work email.
        </EmptyState>
      </Page>
    );

  const ready = title.trim().length >= 3 && skills.length > 0;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (ready) post.mutate();
  };

  return (
    <Page>
      <PageHeader title="Post a job" intro="Students are matched to it on the skills you pick, not on their college." />
      <form onSubmit={submit} className="flex flex-col gap-6">
        {startups.length > 1 && (
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-semibold">Startup</span>
            <select className={field} value={chosen ?? ""} onChange={(e) => setStartupId(e.target.value)}>
              {startups.map((s) => (
                <option key={s.startup_id} value={s.startup_id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">Role</span>
          <input className={field} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend Engineering Intern" required minLength={3} maxLength={120} />
        </label>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1.5 text-sm font-semibold">Type</legend>
          <div className="flex flex-wrap gap-2">
            {TYPES.map(([key, label]) => (
              <label key={key} className={`inline-flex min-h-11 cursor-pointer items-center rounded-md px-3 text-sm md:min-h-9 ${type === key ? "bg-panel ring-[1.5px] ring-fg ring-inset" : "bg-raised"}`}>
                <input type="radio" name="type" value={key} checked={type === key} onChange={() => setType(key)} className="sr-only" />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="flex flex-col gap-2">
          <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
            <input type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} className="size-5 accent-[var(--accent)]" />
            Paid
          </label>
          {paid && (
            <label className="flex flex-col gap-1.5">
              <span className="text-sm text-fg2">Pay (optional)</span>
              <input className={field} value={pay} onChange={(e) => setPay(e.target.value)} placeholder="e.g. ₹20,000/month" maxLength={60} />
            </label>
          )}
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">What they'll do</span>
          <textarea className={`${field} min-h-32`} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What the work is, who they'll work with, and what they'll ship in the first month." maxLength={4000} />
        </label>
        <ChipPicker
          label="Skills it needs"
          hint="Pick the skills that matter most. Students see which of these they have."
          options={(caps.data ?? []).map((c) => ({ id: c.id, name: c.name, group: c.category }))}
          selected={skills}
          max={6}
          onToggle={(id) => setSkills((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))}
          startOpen
        />
        {post.isError && <ErrorBlock error={post.error} />}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" size="lg" disabled={!ready || post.isPending}>
            {post.isPending ? "Posting…" : "Post job"}
          </Button>
          {!ready && <span className="text-sm text-muted">Add a role name and at least one skill.</span>}
        </div>
      </form>
    </Page>
  );
}
