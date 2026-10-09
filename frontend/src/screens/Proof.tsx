import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas, unwrap } from "../api/client";
import { useCapabilities } from "../api/hooks";
import { ChipPicker } from "../components/Chips";
import {
  BottomSheet,
  Button,
  Card,
  EmptyState,
  ErrorBlock,
  Icon,
  List,
  Modal,
  Section,
  SkeletonBlock,
  SkeletonRows,
  useToast,
} from "../components/ds";
import { ProofItemSummary, RepoSummary, VerifiedChips, VerifiedLabel, dateLabel, githubSummary } from "../components/proof";
import { Page, PageHeader } from "../components/Shell";

type ProofMe = Schemas["ProofMe"];
type GitHub = Schemas["GitHubMe"];
type Repo = Schemas["GitHubRepoOut"];

const KEY = ["proof", "me"];

/** Students: show what you've built. GitHub (connected through GitHub itself, so it's
 *  verified) and other work (portfolio, Behance, Dribbble, case studies). */
export default function Proof() {
  const proof = useQuery({
    queryKey: KEY,
    queryFn: () => unwrap(api.GET("/api/proof/me")),
    // While the first import runs, check our own API (never GitHub) every few seconds.
    refetchInterval: (q) => (q.state.data?.github?.status === "importing" ? 3000 : false),
  });

  return (
    <Page>
      <PageHeader
        title="Proof of work"
        intro="Show what you've built. Founders see this next to your skills, never your college."
      />
      {proof.isPending ? (
        <>
          <SkeletonBlock className="h-48 w-full rounded-xl" />
          <SkeletonRows rows={3} label="Loading your work" />
        </>
      ) : proof.isError ? (
        <ErrorBlock error={proof.error} retry={() => void proof.refetch()} />
      ) : (
        <>
          <GitHubCard proof={proof.data} />
          {proof.data.github && <Repos github={proof.data.github} max={proof.data.max_featured} />}
          <OtherWork items={proof.data.items} />
        </>
      )}
    </Page>
  );
}

function GitHubCard({ proof }: { proof: ProofMe }) {
  const g = proof.github;
  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/api/proof/github/start")),
    onSuccess: (r) => window.location.assign(r.authorize_url),
  });
  const [confirm, setConfirm] = useState(false);

  if (!g) {
    return (
      <Card className="flex flex-col gap-4" aria-label="GitHub">
        <div className="flex items-center gap-2">
          <Icon name="github" size={22} />
          <h2 className="text-lg font-semibold">Connect GitHub</h2>
        </div>
        <p className="text-fg2">
          We read your public repos, the languages you use and pull requests you got merged, and show the skills they
          prove as <span className="font-semibold">Verified by GitHub</span>. Read-only and public data only; you choose
          which repos show, and you can disconnect any time.
        </p>
        {proof.github_available ? (
          <Button variant="primary" icon="github" className="self-start" disabled={start.isPending} onClick={() => start.mutate()}>
            {start.isPending ? "Opening GitHub…" : "Connect GitHub"}
          </Button>
        ) : (
          <p className="rounded-lg bg-raised px-4 py-3 text-sm text-fg2">
            Connecting GitHub isn't set up on this server yet. You can still add other work below.
          </p>
        )}
        {start.isError && <ErrorBlock error={start.error} />}
        <p className="text-sm text-muted">Don't code? A portfolio, Behance or Dribbble link, or a case study counts just as much.</p>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col gap-4" aria-label="GitHub">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon name="github" size={22} />
          <a href={g.profile_url} target="_blank" rel="noreferrer" className="text-lg font-semibold underline-offset-2 hover:underline">
            {g.login}
          </a>
        </div>
        <span className="text-sm text-muted">
          {g.status === "importing" ? "Importing…" : `Updated ${dateLabel(g.fetched_at)}`}
        </span>
      </div>
      {g.status_message && (
        <p role="status" className="rounded-lg bg-raised px-4 py-3 text-sm text-fg2">
          {g.status_message}
        </p>
      )}
      {g.status === "importing" ? (
        <SkeletonBlock className="h-10 w-full" />
      ) : (
        <>
          <p className="text-fg2">{githubSummary(g)}</p>
          {g.verified_capabilities.length > 0 ? (
            <div className="flex flex-col gap-2">
              <VerifiedLabel />
              <VerifiedChips items={g.verified_capabilities} />
            </div>
          ) : (
            <p className="text-sm text-muted">
              No skills verified yet: we need a repo you own with at least 3 of your own commits.
            </p>
          )}
        </>
      )}
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        {g.status === "error" && proof.github_available && (
          <Button size="sm" variant="primary" icon="github" disabled={start.isPending} onClick={() => start.mutate()}>
            Connect again
          </Button>
        )}
        <Button size="sm" variant="danger" onClick={() => setConfirm(true)}>
          Disconnect GitHub
        </Button>
      </div>
      <Disconnect open={confirm} onClose={() => setConfirm(false)} />
    </Card>
  );
}

function Disconnect({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/proof/github")),
    onSuccess: async () => {
      onClose();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: KEY }),
        queryClient.invalidateQueries({ queryKey: ["members", "me"] }),
      ]);
      toast({ message: "GitHub disconnected. Your imported data is deleted." });
    },
  });
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Disconnect GitHub?"
      footer={
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>Keep it</Button>
          <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
            {remove.isPending ? "Disconnecting…" : "Disconnect and delete"}
          </Button>
        </div>
      }
    >
      <p className="text-fg2">
        We'll delete your imported repos and your "Verified by GitHub" skills, and remove Circuit's access on GitHub. You
        can connect again any time.
      </p>
      {remove.isError && <ErrorBlock error={remove.error} />}
    </Modal>
  );
}

function Repos({ github, max }: { github: GitHub; max: number }) {
  if (github.status === "importing") return null;
  const featured = github.repos.filter((r) => r.featured).length;
  return (
    <Section title="Your repos">
      <p className="-mt-1 text-sm text-fg2">
        Feature up to {max} on your profile ({featured} now). Hidden repos aren't shown or used for verified skills.
      </p>
      {github.repos.length === 0 ? (
        <EmptyState icon="github" title="No original repos yet">
          We only count repos you own (not forks) with commits by you. Push something and we'll pick it up at the next
          weekly refresh.
        </EmptyState>
      ) : (
        <List label="Your repos">
          {github.repos.map((r) => (
            <RepoRow key={r.id} repo={r} canFeature={r.featured || featured < max} />
          ))}
        </List>
      )}
    </Section>
  );
}

function RepoRow({ repo, canFeature }: { repo: Repo; canFeature: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const update = useMutation({
    mutationFn: (body: Schemas["GitHubRepoUpdate"]) =>
      unwrap(api.PATCH("/api/proof/github/repos/{repo_id}", { params: { path: { repo_id: repo.id } }, body })),
    onSuccess: async (_, body) => {
      await queryClient.invalidateQueries({ queryKey: KEY });
      void queryClient.invalidateQueries({ queryKey: ["members", "me"] });
      if (body.hidden) {
        toast({
          message: `${repo.name} is hidden.`,
          action: { label: "Undo", onClick: () => update.mutate({ hidden: false }) },
        });
      }
    },
  });
  return (
    <li className={`flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-start ${repo.hidden ? "bg-raised/50" : ""}`}>
      <div className={`min-w-0 flex-1 ${repo.hidden ? "opacity-60" : ""}`}>
        <RepoSummary repo={repo} own />
        {!repo.counts_as_proof && !repo.hidden && (
          <p className="mt-1 text-xs text-muted">Fewer than 3 of your commits, so it doesn't verify skills.</p>
        )}
      </div>
      <div className="flex shrink-0 gap-2">
        {!repo.hidden && (
          <Button
            size="sm"
            aria-pressed={repo.featured}
            aria-label={`${repo.featured ? "Unfeature" : "Feature"} ${repo.name}`}
            disabled={update.isPending || (!repo.featured && !canFeature)}
            onClick={() => update.mutate({ featured: !repo.featured })}
            icon={repo.featured ? "check" : "star"}
          >
            {repo.featured ? "Featured" : "Feature"}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          aria-label={`${repo.hidden ? "Show" : "Hide"} ${repo.name}`}
          disabled={update.isPending}
          onClick={() => update.mutate({ hidden: !repo.hidden })}
          icon="eye"
        >
          {repo.hidden ? "Show" : "Hide"}
        </Button>
      </div>
      {update.isError && <ErrorBlock error={update.error} />}
    </li>
  );
}

function OtherWork({ items }: { items: Schemas["ProofItemOut"][] }) {
  const [adding, setAdding] = useState(false);
  return (
    <Section title="Other work">
      <p className="-mt-1 text-sm text-fg2">
        Portfolio, Behance or Dribbble links, live sites, or a case study in your own words. These show as "Added by
        you".
      </p>
      {items.length === 0 ? (
        <EmptyState
          icon="doc"
          title="Nothing added yet"
          action={
            <Button icon="plus" onClick={() => setAdding(true)}>
              Add work
            </Button>
          }
        >
          One project with a short write-up helps founders see what you can do.
        </EmptyState>
      ) : (
        <>
          <List label="Other work">
            {items.map((i) => (
              <ItemRow key={i.id} item={i} />
            ))}
          </List>
          <Button icon="plus" className="self-start" onClick={() => setAdding(true)}>
            Add work
          </Button>
        </>
      )}
      <AddWork open={adding} onClose={() => setAdding(false)} />
    </Section>
  );
}

function ItemRow({ item }: { item: Schemas["ProofItemOut"] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/proof/items/{item_id}", { params: { path: { item_id: item.id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: KEY });
      void queryClient.invalidateQueries({ queryKey: ["members", "me"] });
      toast({ message: `Removed "${item.title}".` });
    },
  });
  return (
    <li className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-start">
      <div className="min-w-0 flex-1">
        <ProofItemSummary item={item} own />
      </div>
      <Button
        size="sm"
        variant="ghost"
        icon="x"
        aria-label={`Remove ${item.title}`}
        disabled={remove.isPending}
        onClick={() => remove.mutate()}
        className="shrink-0 self-start"
      >
        Remove
      </Button>
      {remove.isError && <ErrorBlock error={remove.error} />}
    </li>
  );
}

const MIN_CASE_STUDY = 40;

function AddWork({ open, onClose }: { open: boolean; onClose: () => void }) {
  const caps = useCapabilities();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const reset = () => {
    setUrl("");
    setTitle("");
    setDescription("");
    setSkills([]);
  };
  const add = useMutation({
    mutationFn: () => {
      const link = url.trim();
      return unwrap(
        api.POST("/api/proof/items", {
          body: {
            url: link ? (/^https?:\/\//i.test(link) ? link : `https://${link}`) : null,
            title: title.trim(),
            description: description.trim(),
            capability_ids: skills,
          },
        }),
      );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: KEY });
      void queryClient.invalidateQueries({ queryKey: ["members", "me"] });
      reset();
      onClose();
      toast({ message: "Added to your proof of work." });
    },
  });
  const noLink = !url.trim();
  const tooShort = noLink && description.trim().length < MIN_CASE_STUDY;
  const canSave = title.trim().length > 0 && !tooShort && !add.isPending;
  const options = (caps.data ?? []).map((c) => ({ id: c.id, name: c.name, group: c.category }));
  const field = "min-h-11 w-full rounded-lg border border-line2 bg-raised px-3 py-2 text-base";

  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title="Add work"
      footer={
        <Button variant="primary" className="w-full" disabled={!canSave} onClick={() => add.mutate()}>
          {add.isPending ? "Saving…" : "Save"}
        </Button>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSave) add.mutate();
        }}
      >
        <label className="flex flex-col gap-1.5">
          <span className="font-semibold">Link</span>
          <span className="text-sm text-muted">Portfolio, Behance, Dribbble or a live site. Leave empty for a case study.</span>
          <input className={field} type="url" inputMode="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-semibold">Title</span>
          <input className={field} value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="font-semibold">What you did</span>
          <span className="text-sm text-muted">
            {noLink ? `A case study needs at least ${MIN_CASE_STUDY} characters.` : "The problem, what you made, and what changed."}
          </span>
          <textarea className={`${field} min-h-28`} value={description} maxLength={2000} onChange={(e) => setDescription(e.target.value)} />
        </label>
        {caps.data && (
          <ChipPicker
            label="Skills it shows"
            hint="Up to 5."
            options={options}
            selected={skills}
            max={5}
            onToggle={(id) => setSkills((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))}
          />
        )}
        {add.isError && <ErrorBlock error={add.error} />}
        <p className="text-sm text-muted">
          GitHub links added here show as plain links. To show "Verified by GitHub", <Link to="/me/proof" onClick={onClose} className="underline underline-offset-2">connect GitHub</Link> instead.
        </p>
      </form>
    </BottomSheet>
  );
}
