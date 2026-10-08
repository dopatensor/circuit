import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Schemas, unwrap } from "../api/client";
import { Rating } from "../components/Rating";
import { Page } from "../components/Shell";
import {
  Avatar,
  BridgeBadge,
  Empty,
  ErrorState,
  Eyebrow,
  Muted,
  Pill,
  PrimaryButton,
  SecondaryButton,
  Skeleton,
  Title,
} from "../components/ui";

type Intro = Schemas["IntroOut"];
type Action = Intro["actions"][number];

const STATUS: Record<Intro["status"], { label: string; tone: "green" | "blue" | "neutral" }> = {
  pending: { label: "Waiting", tone: "blue" },
  forwarded: { label: "Passed on", tone: "blue" },
  accepted: { label: "Accepted", tone: "green" },
  completed: { label: "Done", tone: "green" },
  declined: { label: "Declined", tone: "neutral" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
  expired: { label: "Expired", tone: "neutral" },
};

const LABEL: Record<Exclude<Action, "rate">, string> = {
  forward: "Pass it on",
  accept: "Accept",
  decline: "Decline",
  withdraw: "Withdraw",
};

/** Warm intros (F5): requests you sent, ones waiting for you to pass on, and ones that
 *  reached you, each with what you can do now. */
export default function Intros() {
  const inbox = useQuery({
    queryKey: ["intros"],
    queryFn: () => unwrap(api.GET("/api/intros/me")),
  });

  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Title>Intros</Title>
        <Muted>Warm intros go through someone you both know.</Muted>
      </div>
      {inbox.isPending ? (
        <Skeleton lines={3} className="h-40" />
      ) : inbox.isError ? (
        <ErrorState error={inbox.error} retry={inbox.refetch} />
      ) : (
        <Inbox inbox={inbox.data} />
      )}
    </Page>
  );
}

function Inbox({ inbox }: { inbox: Schemas["IntroInbox"] }) {
  const { capacity: c } = inbox;
  const free = Math.max(c.slots - c.used, 0);
  const sections: [string, Intro[]][] = [
    ["To pass on", inbox.to_forward],
    ["For you", inbox.received],
    ["You asked", inbox.sent],
  ];
  const empty = sections.every(([, list]) => list.length === 0);
  return (
    <>
      <p className="text-sm text-muted" data-testid="intro-capacity">
        {free > 0
          ? `You can take ${free} more ${free === 1 ? "intro" : "intros"} this week.`
          : `Your week is full${c.next_free_at ? ` until ${new Date(c.next_free_at).toLocaleDateString([], { weekday: "long" })}` : ""}. New requests wait politely.`}{" "}
        You've asked for {inbox.sent_this_week} of {inbox.sent_limit} this week.
      </p>
      {empty ? (
        <Empty>No intros yet. Ask for one from any of your matches.</Empty>
      ) : (
        sections.map(([title, list]) =>
          list.length === 0 ? null : (
            <section key={title} aria-label={title} className="flex flex-col gap-3">
              <Eyebrow>{title}</Eyebrow>
              <ul className="flex flex-col gap-3">
                {list.map((i) => (
                  <IntroCard key={i.id} intro={i} />
                ))}
              </ul>
            </section>
          ),
        )
      )}
    </>
  );
}

function IntroCard({ intro: i }: { intro: Intro }) {
  const queryClient = useQueryClient();
  const act = useMutation({
    mutationFn: ({ action, rating }: { action: Action; rating?: number }) => {
      const params = { params: { path: { intro_id: i.id } } };
      switch (action) {
        case "forward":
          return unwrap(api.POST("/api/intros/{intro_id}/forward", params));
        case "accept":
          return unwrap(api.POST("/api/intros/{intro_id}/accept", params));
        case "decline":
          return unwrap(api.POST("/api/intros/{intro_id}/decline", params));
        case "withdraw":
          return unwrap(api.POST("/api/intros/{intro_id}/withdraw", params));
        case "rate":
          return unwrap(api.POST("/api/intros/{intro_id}/rate", { ...params, body: { rating: rating! } }));
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["intros"] }),
  });
  const people = [i.sender, i.via, i.target].filter((p): p is NonNullable<typeof p> => p !== null);
  const status = STATUS[i.status];
  const headline =
    i.my_role === "sender"
      ? `You asked to meet ${i.target.display_name}`
      : i.my_role === "mutual"
        ? `${i.sender.display_name} wants to meet ${i.target.display_name}`
        : `${i.sender.display_name} wants to meet you`;
  const buttons = i.actions.filter((a): a is Exclude<Action, "rate"> => a !== "rate");
  const main = buttons.find((a) => a === "forward" || a === "accept");

  return (
    <li className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">{headline}</h3>
        <Pill tone={status.tone}>{status.label}</Pill>
      </div>
      <ol aria-label="Intro path" className="flex flex-wrap items-center gap-2 text-sm">
        {people.map((p, n) => (
          <li key={p.id} className="flex items-center gap-2">
            {n > 0 && (
              <span aria-hidden="true" className="text-muted">
                →
              </span>
            )}
            <Avatar name={p.display_name} size="sm" />
            <span className={i.via && p.id === i.via.id ? "font-semibold text-blue" : ""}>
              {p.display_name}
            </span>
          </li>
        ))}
      </ol>
      <blockquote className="border-l-2 border-line pl-3 text-muted">{i.reason}</blockquote>
      {i.is_bridge && (
        <div>
          <BridgeBadge />
        </div>
      )}
      {i.outcome_rating !== null && (
        <p className="text-sm text-muted">You rated it {i.outcome_rating} of 5.</p>
      )}
      {act.isError && <ErrorState error={act.error} />}
      {buttons.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {buttons.map((a) =>
            a === main ? (
              <PrimaryButton key={a} disabled={act.isPending} onClick={() => act.mutate({ action: a })}>
                {LABEL[a]}
              </PrimaryButton>
            ) : (
              <SecondaryButton key={a} disabled={act.isPending} onClick={() => act.mutate({ action: a })}>
                {LABEL[a]}
              </SecondaryButton>
            ),
          )}
        </div>
      )}
      {i.actions.includes("rate") && (
        <Rating
          question={`How useful was meeting ${i.target.display_name}?`}
          disabled={act.isPending}
          onRate={(rating) => act.mutate({ action: "rate", rating })}
        />
      )}
    </li>
  );
}
