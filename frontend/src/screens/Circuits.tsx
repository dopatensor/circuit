import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Schemas, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { Rating } from "../components/Rating";
import { Page } from "../components/Shell";
import {
  Avatar,
  Empty,
  ErrorState,
  Muted,
  Pill,
  PrimaryButton,
  SecondaryButton,
  Skeleton,
  Title,
} from "../components/ui";

type Circuit = Schemas["CircuitCard"];
type Leg = Schemas["CircuitLegOut"];

const STATUS: Record<Circuit["status"], { label: string; tone: "green" | "blue" | "neutral" }> = {
  proposed: { label: "Waiting for answers", tone: "blue" },
  active: { label: "Active", tone: "green" },
  completed: { label: "Done", tone: "green" },
  declined: { label: "Called off", tone: "neutral" },
  expired: { label: "Expired", tone: "neutral" },
};

/** "Marketing" -> "marketing", but keep acronyms like "UX research" (as the API does). */
const lowerFirst = (s: string) => (/^.[A-Z]/.test(s) ? s : s.charAt(0).toLowerCase() + s.slice(1));

/** Exchange circuits (F6): three people who can each help the next one, in a loop. */
export default function Circuits() {
  const circuits = useQuery({
    queryKey: ["circuits"],
    queryFn: () => unwrap(api.GET("/api/circuits/me")),
  });
  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Title>Circuits</Title>
        <Muted>You help one person, someone else helps you. Three people, one loop.</Muted>
      </div>
      {circuits.isPending ? (
        <Skeleton lines={2} className="h-72" />
      ) : circuits.isError ? (
        <ErrorState error={circuits.error} retry={circuits.refetch} />
      ) : circuits.data.length === 0 ? (
        <Empty>
          No circuits yet. Each week we look for three people who can help each other in a loop.
        </Empty>
      ) : (
        <ul className="flex flex-col gap-4">
          {circuits.data.map((c) => (
            <LoopCard key={c.id} circuit={c} />
          ))}
        </ul>
      )}
    </Page>
  );
}

function hoursLeft(expiresAt: string) {
  return Math.max(0, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 3_600_000));
}

function LoopCard({ circuit: c }: { circuit: Circuit }) {
  const { member } = useAuth();
  const queryClient = useQueryClient();
  const me = member?.id;
  const act = useMutation({
    mutationFn: ({ action, rating }: { action: Circuit["actions"][number]; rating?: number }) => {
      const params = { params: { path: { circuit_id: c.id } } };
      if (action === "accept") return unwrap(api.POST("/api/circuits/{circuit_id}/accept", params));
      if (action === "decline") return unwrap(api.POST("/api/circuits/{circuit_id}/decline", params));
      return unwrap(api.POST("/api/circuits/{circuit_id}/rate", { ...params, body: { rating: rating! } }));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["circuits"] }),
  });
  const who = (p: Leg["giver"], start: boolean) =>
    p.id === me ? (start ? "You" : "you") : p.display_name;
  const line = (l: Leg) =>
    `${who(l.giver, true)} ${l.giver.id === me ? "help" : "helps"} ${who(l.receiver, false)} with ${lowerFirst(l.capability.name)}`;
  const incoming = c.legs.find((l) => l.receiver.id === me);
  const status = STATUS[c.status];
  const hours = hoursLeft(c.expires_at);

  return (
    <li className="flex flex-col gap-5 rounded-2xl border border-line bg-surface p-5" data-testid="loop-card">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-semibold">Your circuit</h2>
        <Pill tone={status.tone}>{status.label}</Pill>
      </div>

      <LoopDiagram people={c.legs.map((l) => l.giver)} me={me} />

      <ol aria-label="Who helps whom" className="flex flex-col gap-2">
        {c.legs.map((l) => (
          <li
            key={l.position}
            className="flex items-center justify-between gap-3 rounded-xl border border-line bg-raised px-4 py-3"
          >
            <span>{line(l)}</span>
            {c.status === "proposed" ? (
              <Pill tone={l.consent === "accepted" ? "green" : "neutral"}>
                {l.consent === "accepted" ? "Accepted" : l.consent === "declined" ? "Declined" : "Waiting"}
              </Pill>
            ) : l.fulfilled ? (
              <Pill tone="green">Done{l.rating ? ` · ${l.rating}/5` : ""}</Pill>
            ) : null}
          </li>
        ))}
      </ol>

      {act.isError && <ErrorState error={act.error} />}
      {c.actions.includes("accept") && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            Answer within {hours} {hours === 1 ? "hour" : "hours"}. If one person declines, the
            circuit is called off for all three.
          </p>
          <div className="flex flex-wrap gap-3">
            <PrimaryButton disabled={act.isPending} onClick={() => act.mutate({ action: "accept" })}>
              Accept
            </PrimaryButton>
            <SecondaryButton disabled={act.isPending} onClick={() => act.mutate({ action: "decline" })}>
              Decline
            </SecondaryButton>
          </div>
        </div>
      )}
      {c.status === "proposed" && c.my_consent === "accepted" && (
        <p className="text-sm text-green">You accepted. Waiting for the others.</p>
      )}
      {c.actions.includes("rate") && incoming && (
        <Rating
          question={`Rate the help you got from ${incoming.giver.display_name} with ${lowerFirst(incoming.capability.name)}.`}
          disabled={act.isPending}
          onRate={(rating) => act.mutate({ action: "rate", rating })}
        />
      )}
    </li>
  );
}

// Three points on a circle, starting at the top and going clockwise.
const ANGLES = [-90, 30, 150];
const R = 70;
const point = (deg: number, r = R) => {
  const a = (deg * Math.PI) / 180;
  return { x: 100 + r * Math.cos(a), y: 100 + r * Math.sin(a) };
};

/** The loop as three names in a simple circle, arrows going clockwise. */
function LoopDiagram({ people, me }: { people: Leg["giver"][]; me?: string }) {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-64" aria-hidden="true">
      <svg viewBox="0 0 200 200" className="absolute inset-0 size-full text-line">
        {ANGLES.map((a, i) => {
          const fromDeg = a + 28;
          const toDeg = ANGLES[(i + 1) % 3] + (i === 2 ? 360 : 0) - 28;
          const from = point(fromDeg);
          const to = point(toDeg);
          // Arrowhead halfway along, pointing along the circle (clockwise).
          const midDeg = (fromDeg + toDeg) / 2;
          const t = (midDeg * Math.PI) / 180;
          const dir = { x: -Math.sin(t), y: Math.cos(t) };
          const side = { x: -dir.y, y: dir.x };
          const mid = point(midDeg);
          const tip = { x: mid.x + dir.x * 8, y: mid.y + dir.y * 8 };
          const back = { x: mid.x - dir.x * 6, y: mid.y - dir.y * 6 };
          const head = [
            tip,
            { x: back.x + side.x * 4.5, y: back.y + side.y * 4.5 },
            { x: back.x - side.x * 4.5, y: back.y - side.y * 4.5 },
          ];
          return (
            <g key={a}>
              <path
                d={`M ${from.x} ${from.y} A ${R} ${R} 0 0 1 ${to.x} ${to.y}`}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              />
              <polygon points={head.map((q) => `${q.x},${q.y}`).join(" ")} className="fill-blue" />
            </g>
          );
        })}
      </svg>
      {people.map((p, i) => {
        const { x, y } = point(ANGLES[i]);
        return (
          <div
            key={p.id}
            className="absolute flex w-24 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 text-center"
            style={{ left: `${x / 2}%`, top: `${y / 2}%` }}
          >
            <Avatar name={p.display_name} size="sm" />
            <span className={`text-sm leading-tight ${p.id === me ? "font-semibold text-green" : ""}`}>
              {p.id === me ? "You" : p.display_name.split(" ")[0]}
            </span>
          </div>
        );
      })}
    </div>
  );
}
