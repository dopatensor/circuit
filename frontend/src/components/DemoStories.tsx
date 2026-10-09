import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { api, ApiError, type Schemas, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { HOME, ROLE_LABEL } from "../nav";
import { Avatar, Empty, ErrorState, Skeleton } from "./ui";

type Persona = Schemas["Persona"];

export function usePersonas() {
  return useQuery({
    queryKey: ["personas"],
    queryFn: () => unwrap(api.GET("/api/auth/demo/personas")),
    retry: false,
    staleTime: Infinity,
  });
}

function byStory(personas: Persona[]) {
  const stories = new Map<number, { title: string; people: Persona[] }>();
  for (const p of personas) {
    const story = stories.get(p.story_number) ?? { title: p.story_title, people: [] };
    story.people.push(p);
    stories.set(p.story_number, story);
  }
  return [...stories.entries()];
}

/** Demo mode (F9): the prepared people, grouped by the five demo stories. One tap
 *  signs in as that person and opens their main tab. */
export function DemoStories({ onSwitched }: { onSwitched?: () => void }) {
  const { member, login } = useAuth();
  const navigate = useNavigate();
  const personas = usePersonas();
  const switchTo = useMutation({
    mutationFn: login,
    onSuccess: () => {
      onSwitched?.();
      navigate(HOME);
    },
  });

  if (personas.isPending) return <Skeleton lines={3} className="h-40" />;
  if (personas.error instanceof ApiError && personas.error.status === 404)
    return <Empty>Demo sign-in is turned off on this server.</Empty>;
  if (personas.error) return <ErrorState error={personas.error} retry={personas.refetch} />;
  if (personas.data.length === 0)
    return <Empty>No demo people yet. Run make reset-demo on the server.</Empty>;

  return (
    <div className="flex flex-col gap-4">
      {switchTo.error && <ErrorState error={switchTo.error} />}
      {byStory(personas.data).map(([number, story]) => (
        <section
          key={number}
          aria-label={`Story ${number}: ${story.title}`}
          className="rounded-xl border border-line bg-surface"
        >
          <header className="flex items-baseline gap-3 px-4 pt-4 pb-2">
            <span className="text-xs font-semibold tracking-[0.06em] text-muted uppercase">Story {number}</span>
            <h3 className="text-base font-semibold">{story.title}</h3>
          </header>
          <ul className="flex flex-col px-2 pb-2">
            {story.people.map((p) => {
              const current = member?.id === p.member_id;
              const busy = switchTo.isPending && switchTo.variables === p.key;
              return (
                <li key={p.key}>
                  <button
                    disabled={current || switchTo.isPending}
                    onClick={() => switchTo.mutate(p.key)}
                    className="group flex min-h-16 w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-raised disabled:cursor-default disabled:hover:bg-transparent"
                  >
                    <Avatar name={p.display_name} />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-base font-medium">{p.display_name}</span>
                      <span className="text-sm text-muted">
                        {ROLE_LABEL[p.role]} · {p.story}
                      </span>
                    </span>
                    <span
                      className={`shrink-0 rounded px-2 py-0.5 text-sm font-medium ${
                        current
                          ? "text-fg ring-1 ring-line2 ring-inset"
                          : "border border-line text-fg group-hover:border-fg2"
                      }`}
                    >
                      {current ? "You" : busy ? "Opening…" : "Open"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
