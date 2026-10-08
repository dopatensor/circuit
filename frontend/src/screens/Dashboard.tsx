import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import { Page } from "../components/Shell";
import { Card, Empty, ErrorState, Eyebrow, Muted, PrimaryButton, Title } from "../components/ui";

/** Partner dashboard. Phase 10 adds the admin "Run round now" for exchange circuits;
 *  the gap chart, map and stats arrive in the next build. */
export default function Dashboard() {
  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Title>Dashboard</Title>
        <Muted>What your ecosystem has, and what it lacks.</Muted>
      </div>
      <RunRound />
      <Empty>Capability gaps, the gap map and network stats arrive in a coming build.</Empty>
    </Page>
  );
}

/** The weekly circuit round, on demand (for demos). */
function RunRound() {
  const queryClient = useQueryClient();
  const run = useMutation({
    mutationFn: () => unwrap(api.POST("/api/admin/circuits/run")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["circuits"] }),
  });
  const r = run.data;
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Eyebrow>Exchange circuits</Eyebrow>
        <p>Find loops of three people who can each help the next, and propose them now.</p>
      </div>
      <PrimaryButton className="self-start" disabled={run.isPending} onClick={() => run.mutate()}>
        {run.isPending ? "Running…" : "Run round now"}
      </PrimaryButton>
      {run.isError && <ErrorState error={run.error} />}
      {r && (
        <div role="status" className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            Round {r.round_key}: {r.pool} people could exchange help, {r.cycles_found} possible{" "}
            {r.cycles_found === 1 ? "loop" : "loops"}.{" "}
            {r.circuits.length === 0
              ? "No new circuits this time (people already in a circuit are left out)."
              : `${r.circuits.length} proposed. Each person has 72 hours to accept.`}
          </p>
          {r.circuits.length > 0 && (
            <ul className="flex flex-col gap-2">
              {r.circuits.map((c, i) => (
                <li key={c.id ?? i} className="rounded-xl border border-line bg-raised px-4 py-3">
                  {c.sentence}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}
