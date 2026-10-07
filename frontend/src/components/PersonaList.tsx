import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { api, ApiError, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { ROLE_LABEL, tabsFor } from "../nav";
import { Empty, ErrorState, Skeleton } from "./ui";

/** Demo mode (F9): sign in as a prepared person in one tap. */
export function PersonaList() {
  const { member, login } = useAuth();
  const navigate = useNavigate();
  const personas = useQuery({
    queryKey: ["personas"],
    queryFn: () => unwrap(api.GET("/api/auth/demo/personas")),
    retry: false,
  });
  const switchTo = useMutation({
    mutationFn: login,
    onSuccess: (m) => navigate(tabsFor(m.role)[0].to),
  });

  if (personas.isPending) return <Skeleton lines={4} />;
  if (personas.error instanceof ApiError && personas.error.status === 404)
    return <Empty>Demo sign-in is turned off on this server.</Empty>;
  if (personas.error) return <ErrorState error={personas.error} retry={personas.refetch} />;
  if (personas.data.length === 0)
    return <Empty>No demo people yet. Run make reset-demo on the server.</Empty>;

  return (
    <section aria-label="Demo people" className="flex flex-col gap-2">
      {switchTo.error && <ErrorState error={switchTo.error} />}
      <ul className="flex flex-col divide-y divide-line border-y border-line">
        {personas.data.map((p) => {
          const current = member?.id === p.member_id;
          return (
            <li key={p.key}>
              <button
                disabled={current || switchTo.isPending}
                onClick={() => switchTo.mutate(p.key)}
                className="flex min-h-16 w-full items-center gap-4 py-3 text-left disabled:cursor-default"
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-base font-medium">{p.display_name}</span>
                  <span className="text-sm text-muted">
                    {ROLE_LABEL[p.role]} · {p.story}
                  </span>
                </span>
                <span className="shrink-0 text-sm text-muted">
                  {current ? "You" : switchTo.variables === p.key ? "…" : "Use"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
