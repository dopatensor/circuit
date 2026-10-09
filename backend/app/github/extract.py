"""Turn GitHub's JSON into the facts we keep. Pure functions, no network or database.

What counts:
- original repos only: owned by the connected account (matched on GitHub's numeric
  account id, not the name) and not forks;
- the student's own commits in them (a repo with none of their commits proves nothing);
- languages and frameworks, mapped onto our capability list;
- merged pull requests to repos the student doesn't own;
- recent activity (weeks with pushes or pull requests in the last 90 days);
- README excerpts and homepage links, to show on the profile.

Stars and follower counts are never read: popularity isn't skill.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

# A repo needs at least this many of the student's commits to verify a capability.
MIN_USER_COMMITS = 3
# A language must be at least this share of a repo's code to count for it.
MIN_LANGUAGE_SHARE = 0.2
README_EXCERPT_CHARS = 280
ACTIVITY_DAYS = 90
ACTIVITY_EVENTS = {"PushEvent", "PullRequestEvent"}

# Languages GitHub detects -> the capability they show. Languages that say little on
# their own (Shell, Markdown, Makefile) are left out.
LANGUAGE_CAPABILITIES: dict[str, str] = {
    "Python": "backend_development",
    "Go": "backend_development",
    "Java": "backend_development",
    "Ruby": "backend_development",
    "PHP": "backend_development",
    "Rust": "backend_development",
    "C#": "backend_development",
    "Elixir": "backend_development",
    "Scala": "data_engineering",
    "PLpgSQL": "data_engineering",
    "TypeScript": "frontend_development",
    "JavaScript": "frontend_development",
    "HTML": "frontend_development",
    "CSS": "frontend_development",
    "SCSS": "frontend_development",
    "Vue": "frontend_development",
    "Svelte": "frontend_development",
    "Kotlin": "mobile_development",
    "Swift": "mobile_development",
    "Dart": "mobile_development",
    "Objective-C": "mobile_development",
    "C": "embedded_hardware",
    "C++": "embedded_hardware",
    "Assembly": "embedded_hardware",
    "Verilog": "embedded_hardware",
    "VHDL": "embedded_hardware",
    "Jupyter Notebook": "data_analysis",
    "R": "data_analysis",
    "Dockerfile": "devops_cloud",
    "HCL": "devops_cloud",
}

# Frameworks and tools, found in a repo's topics, description or README.
# Display name -> (capability, keywords matched as whole words, case-insensitive).
FRAMEWORKS: dict[str, tuple[str, tuple[str, ...]]] = {
    "React": ("frontend_development", ("react", "reactjs", "next.js", "nextjs")),
    "Vue": ("frontend_development", ("vue", "vuejs", "nuxt")),
    "Angular": ("frontend_development", ("angular",)),
    "Svelte": ("frontend_development", ("svelte", "sveltekit")),
    "Tailwind CSS": ("frontend_development", ("tailwind", "tailwindcss")),
    "FastAPI": ("backend_development", ("fastapi",)),
    "Django": ("backend_development", ("django",)),
    "Flask": ("backend_development", ("flask",)),
    "Express": ("backend_development", ("express", "expressjs")),
    "Spring": ("backend_development", ("spring", "spring-boot", "springboot")),
    "Rails": ("backend_development", ("rails", "ruby-on-rails")),
    "Laravel": ("backend_development", ("laravel",)),
    "PostgreSQL": ("backend_development", ("postgres", "postgresql")),
    "pandas": ("data_analysis", ("pandas",)),
    "Power BI": ("data_analysis", ("powerbi", "power-bi")),
    "PyTorch": ("machine_learning", ("pytorch", "torch")),
    "TensorFlow": ("machine_learning", ("tensorflow", "keras")),
    "scikit-learn": ("machine_learning", ("scikit-learn", "sklearn")),
    "Hugging Face": ("machine_learning", ("huggingface", "hugging-face", "transformers")),
    "Airflow": ("data_engineering", ("airflow",)),
    "Spark": ("data_engineering", ("spark", "pyspark")),
    "dbt": ("data_engineering", ("dbt",)),
    "Kafka": ("data_engineering", ("kafka",)),
    "Docker": ("devops_cloud", ("docker", "dockerfile", "docker-compose")),
    "Kubernetes": ("devops_cloud", ("kubernetes", "k8s", "helm")),
    "Terraform": ("devops_cloud", ("terraform",)),
    "GitHub Actions": ("devops_cloud", ("github-actions",)),
    "Flutter": ("mobile_development", ("flutter",)),
    "React Native": ("mobile_development", ("react-native",)),
    "Android": ("mobile_development", ("android",)),
    "SwiftUI": ("mobile_development", ("swiftui",)),
    "Arduino": ("embedded_hardware", ("arduino", "esp32", "esp8266", "raspberry-pi")),
    "pytest": ("qa_testing", ("pytest",)),
    "Playwright": ("qa_testing", ("playwright",)),
    "Cypress": ("qa_testing", ("cypress",)),
    "Selenium": ("qa_testing", ("selenium",)),
}


@dataclass(frozen=True)
class RepoFacts:
    """What we keep about one original repo."""

    github_repo_id: int
    name: str
    html_url: str
    description: str
    homepage_url: str | None
    primary_language: str | None
    languages: dict[str, int]
    frameworks: list[str]
    commits_by_user: int
    commits_total: int
    readme_excerpt: str
    pushed_at: datetime | None


@dataclass(frozen=True)
class VerifiedCapability:
    capability_id: str
    evidence: list[str]  # languages and frameworks, e.g. ["Python", "FastAPI"]
    repo_count: int


@dataclass(frozen=True)
class Activity:
    active_weeks: int
    last_active_at: datetime | None


@dataclass(frozen=True)
class ExternalPRs:
    total: int
    items: list[dict] = field(default_factory=list)  # [{"repo", "url", "merged_at"}]


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def original_repos(repos: Iterable[dict], github_user_id: int) -> list[dict]:
    """Repos owned by this exact account (by id, so a renamed or look-alike account
    can't slip in) that aren't forks."""
    return [
        r for r in repos if not r.get("fork") and (r.get("owner") or {}).get("id") == github_user_id
    ]


def commit_counts(contributors: Iterable[dict], github_user_id: int) -> tuple[int, int]:
    """(the student's commits, everyone's commits) on the default branch."""
    mine = total = 0
    for c in contributors:
        n = int(c.get("contributions", 0))
        total += n
        if c.get("id") == github_user_id:
            mine += n
    return mine, total


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9.+#-]*[a-z0-9+#]|[a-z0-9]", text.lower()))


def detect_frameworks(topics: Iterable[str], description: str, readme: str) -> list[str]:
    words = _words(" ".join([*topics, description or "", readme or ""]))
    return [name for name, (_, keys) in FRAMEWORKS.items() if any(k in words for k in keys)]


_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_MD_LINE_START = re.compile(r"^[#>\-*+\s]+", re.MULTILINE)  # headings, quotes, bullets
_MD_INLINE = re.compile(r"[`*~|]|(?<!\w)_|_(?!\w)")  # keeps snake_case words


def readme_excerpt(raw: str, limit: int = README_EXCERPT_CHARS) -> str:
    """The README as one short line of plain text (badges, images and markup removed)."""
    text = _MD_IMAGE.sub("", raw or "")
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = _MD_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub(" ", text)
    text = _MD_LINE_START.sub(" ", text)
    text = _MD_INLINE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def clean_url(value: str | None) -> str | None:
    """Homepage links: only http(s), with a scheme added when GitHub has none."""
    value = (value or "").strip()
    if not value:
        return None
    if not re.match(r"^https?://", value, re.IGNORECASE):
        if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", value, re.IGNORECASE):
            return None  # another scheme (javascript:, mailto:, ...)
        value = "https://" + value
    host = re.match(r"^https?://([^/\s?#:]+)", value, re.IGNORECASE)
    if not host or "." not in host.group(1) or " " in value or len(value) > 300:
        return None
    return value


def repo_facts(
    repo: dict, languages: dict[str, int], contributors: list[dict], readme: str, user_id: int
) -> RepoFacts:
    mine, total = commit_counts(contributors, user_id)
    return RepoFacts(
        github_repo_id=int(repo["id"]),
        name=str(repo["name"])[:200],
        html_url=str(repo["html_url"])[:300],
        description=(repo.get("description") or "")[:500],
        homepage_url=clean_url(repo.get("homepage")),
        primary_language=repo.get("language"),
        languages={k: int(v) for k, v in languages.items()},
        frameworks=detect_frameworks(
            repo.get("topics") or [], repo.get("description") or "", readme
        ),
        commits_by_user=mine,
        commits_total=total,
        readme_excerpt=readme_excerpt(readme),
        pushed_at=parse_time(repo.get("pushed_at")),
    )


def counts_as_proof(repo: RepoFacts) -> bool:
    return repo.commits_by_user >= MIN_USER_COMMITS


def repo_languages(repo: RepoFacts) -> list[str]:
    """Languages that make up a real share of this repo's code."""
    total = sum(repo.languages.values())
    if total <= 0:
        return [repo.primary_language] if repo.primary_language else []
    return [name for name, size in repo.languages.items() if size / total >= MIN_LANGUAGE_SHARE]


def verified_capabilities(repos: Iterable[RepoFacts]) -> list[VerifiedCapability]:
    """Capabilities shown by repos with enough of the student's own commits.

    Sorted by how many repos show each one."""
    evidence: dict[str, dict[str, None]] = {}
    repo_ids: dict[str, set[int]] = {}
    for repo in repos:
        if not counts_as_proof(repo):
            continue
        found = [(LANGUAGE_CAPABILITIES.get(lang), lang) for lang in repo_languages(repo)]
        found += [(FRAMEWORKS[f][0], f) for f in repo.frameworks if f in FRAMEWORKS]
        for cap, name in found:
            if cap is None:
                continue
            evidence.setdefault(cap, {})[name] = None
            repo_ids.setdefault(cap, set()).add(repo.github_repo_id)
    out = [
        VerifiedCapability(cap, list(names), len(repo_ids[cap])) for cap, names in evidence.items()
    ]
    return sorted(out, key=lambda v: (-v.repo_count, v.capability_id))


def external_prs(total: int, items: Iterable[dict], login: str, keep: int = 10) -> ExternalPRs:
    """Merged pull requests to repos owned by someone else."""
    kept = []
    dropped = 0
    for item in items:
        # repository_url: https://api.github.com/repos/{owner}/{repo}
        parts = str(item.get("repository_url", "")).rstrip("/").split("/")
        merged_at = (item.get("pull_request") or {}).get("merged_at")
        if len(parts) < 2 or parts[-2].lower() == login.lower() or not merged_at:
            dropped += 1  # the search should already leave these out; be safe
            continue
        kept.append(
            {
                "repo": f"{parts[-2]}/{parts[-1]}",
                "url": item.get("html_url"),
                "merged_at": merged_at,
            }
        )
    return ExternalPRs(total=max(total - dropped, len(kept)), items=kept[:keep])


def activity(events: Iterable[dict], now: datetime | None = None) -> Activity:
    """Weeks with pushes or pull requests in the last 90 days, and the latest one."""
    now = now or datetime.now(UTC)
    since = now - timedelta(days=ACTIVITY_DAYS)
    weeks: set[tuple[int, int]] = set()
    latest: datetime | None = None
    for e in events:
        if e.get("type") not in ACTIVITY_EVENTS:
            continue
        at = parse_time(e.get("created_at"))
        if at is None or at < since:
            continue
        weeks.add(at.isocalendar()[:2])
        latest = max(latest, at) if latest else at
    return Activity(active_weeks=len(weeks), last_active_at=latest)
