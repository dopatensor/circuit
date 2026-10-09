import type { Schemas } from "../api/client";
import { useCapabilities } from "../api/hooks";
import { Badge, Icon, type IconName } from "./ds";

// Proof of work (R2): the pieces shared by your proof page, public profiles and the
// founders' applicant list.

type Repo = Schemas["GitHubRepoOut"];
type Item = Schemas["ProofItemOut"];
type Verified = Schemas["VerifiedCapabilityOut"];
type GitHub = Schemas["GitHubPublic"];

const KIND: Record<Item["kind"], { label: string; icon: IconName }> = {
  portfolio: { label: "Portfolio", icon: "link" },
  behance: { label: "Behance", icon: "link" },
  dribbble: { label: "Dribbble", icon: "link" },
  case_study: { label: "Case study", icon: "doc" },
  website: { label: "Website", icon: "link" },
  code: { label: "Code link", icon: "link" },
  other: { label: "Link", icon: "link" },
};

/** "Verified by GitHub" skills: a GitHub mark and the evidence ("Python, FastAPI"). */
export function VerifiedChips({ items, compact = false }: { items: Verified[] | string[]; compact?: boolean }) {
  const caps = useCapabilities();
  if (items.length === 0) return null;
  return (
    <ul aria-label="Verified by GitHub" className="flex flex-wrap gap-2">
      {items.map((v) => {
        const id = typeof v === "string" ? v : v.capability_id;
        const evidence = typeof v === "string" ? [] : v.evidence;
        return (
          <li key={id}>
            <span
              title={evidence.length ? `Verified by GitHub: ${evidence.join(", ")}` : "Verified by GitHub"}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-md px-3 text-sm ring-1 ring-line2 ring-inset"
            >
              <Icon name="github" size={14} />
              <span className="font-semibold">{caps.name(id)}</span>
              {!compact && evidence.length > 0 && <span className="text-xs text-muted">{evidence.slice(0, 3).join(", ")}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** "Verified by GitHub" as a small heading line, so the chips never stand unexplained. */
export function VerifiedLabel() {
  return (
    <p className="flex items-center gap-1.5 text-xs font-semibold tracking-[0.06em] text-muted uppercase">
      <Icon name="check" size={13} /> Verified by GitHub
    </p>
  );
}

export function commitsLine(r: Repo) {
  if (r.commits_total > r.commits_by_user) return `${r.commits_by_user} of ${r.commits_total} commits theirs`;
  return `${r.commits_by_user} ${r.commits_by_user === 1 ? "commit" : "commits"}`;
}

/** One repo: name (links to GitHub), languages and frameworks, commits, the README line. */
export function RepoSummary({ repo, own = false }: { repo: Repo; own?: boolean }) {
  const tech = [...repo.languages.slice(0, 2), ...repo.frameworks.slice(0, 3)];
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <a href={repo.html_url} target="_blank" rel="noreferrer" className="font-semibold break-words underline-offset-2 hover:underline">
        {repo.name}
      </a>
      <p className="text-sm text-muted">
        {[tech.join(", "), own ? commitsLine(repo).replace("theirs", "yours") : commitsLine(repo)].filter(Boolean).join(" · ")}
      </p>
      {(repo.readme_excerpt || repo.description) && (
        <p className="text-sm text-fg2">{repo.readme_excerpt || repo.description}</p>
      )}
      {repo.homepage_url && (
        <a href={repo.homepage_url} target="_blank" rel="noreferrer" className="text-sm text-fg2 underline underline-offset-2 hover:text-fg">
          {repo.homepage_url.replace(/^https?:\/\//, "")}
        </a>
      )}
    </div>
  );
}

/** A non-code proof item. Always labelled "Added by you/them": we don't verify these. */
export function ProofItemSummary({ item, own = false }: { item: Item; own?: boolean }) {
  const caps = useCapabilities();
  const kind = KIND[item.kind];
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {item.url ? (
          <a href={item.url} target="_blank" rel="noreferrer" className="font-semibold break-words underline-offset-2 hover:underline">
            {item.title}
          </a>
        ) : (
          <span className="font-semibold">{item.title}</span>
        )}
        <Badge icon={kind.icon}>{kind.label}</Badge>
      </div>
      {item.description && <p className="text-sm text-fg2">{item.description}</p>}
      <p className="text-xs text-muted">
        {[own ? "Added by you" : "Added by them", ...item.capability_ids.map((c) => caps.name(c))].join(" · ")}
      </p>
    </div>
  );
}

/** One sentence about the GitHub evidence: repos, pull requests, recent activity. */
export function githubSummary(g: GitHub) {
  const parts = [`${g.original_repos} original ${g.original_repos === 1 ? "repo" : "repos"} with their own commits`];
  if (g.external_prs_total > 0)
    parts.push(`${g.external_prs_total} merged pull ${g.external_prs_total === 1 ? "request" : "requests"} to other projects`);
  parts.push(g.active_weeks_90d > 0 ? `active ${g.active_weeks_90d} of the last 13 weeks` : "no public activity in the last 3 months");
  return parts.join(" · ");
}

export function dateLabel(iso: string | null | undefined) {
  if (!iso) return "never";
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
