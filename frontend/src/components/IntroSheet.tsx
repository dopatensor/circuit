import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { useAuth } from "../auth";
import { Sheet } from "./Sheet";
import { Avatar, ErrorState, PrimaryButton, Skeleton } from "./ui";

/** "Ask for intro" (F5): how the request would travel (through the best mutual
 *  connection when there is one), a short reason, and Send. */
export function IntroSheet({
  memberId,
  name,
  onClose,
}: {
  memberId: string | null;
  name: string;
  onClose: () => void;
}) {
  return (
    <Sheet open={memberId !== null} onClose={onClose} title={`Intro to ${name}`}>
      {memberId && <IntroForm key={memberId} memberId={memberId} />}
    </Sheet>
  );
}

function IntroForm({ memberId }: { memberId: string }) {
  const { member } = useAuth();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const path = useQuery({
    queryKey: ["intro-path", memberId],
    queryFn: () =>
      unwrap(api.GET("/api/intros/path/{member_id}", { params: { path: { member_id: memberId } } })),
    staleTime: 0,
  });
  const send = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/intros", { body: { to_member_id: memberId, reason: reason.trim() } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["intros"] });
      void queryClient.invalidateQueries({ queryKey: ["intro-path", memberId] });
      void queryClient.invalidateQueries({ queryKey: ["me-stat"] });
    },
  });

  if (path.isPending) return <Skeleton lines={2} className="h-20" />;
  if (path.isError) return <ErrorState error={path.error} retry={path.refetch} />;
  const p = path.data;
  const chain = [member?.display_name ?? "You", p.via?.display_name, p.target.display_name].filter(
    (x): x is string => Boolean(x),
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3" data-testid="intro-path">
        <ol aria-label="Intro path" className="flex flex-wrap items-center gap-2">
          {chain.map((n, i) => (
            <li key={n} className="flex items-center gap-2">
              {i > 0 && (
                <span aria-hidden="true" className="text-muted">
                  →
                </span>
              )}
              <Avatar name={n} size="sm" />
              <span className={`text-sm ${i === 1 && p.via ? "font-semibold text-blue" : ""}`}>
                {i === 0 ? "You" : n}
              </span>
            </li>
          ))}
        </ol>
        <p>{p.sentence}</p>
      </div>

      {send.isSuccess ? (
        <div role="status" className="flex flex-col gap-3 rounded-2xl border border-green/30 bg-green/10 p-4">
          <p className="text-green">
            {send.data.via
              ? `Sent. ${send.data.via.display_name} will see it first and pass it on.`
              : `Sent to ${send.data.target.display_name}.`}
          </p>
          <Link to="/intros" className="text-sm font-semibold text-blue hover:underline">
            See it in Intros
          </Link>
        </div>
      ) : p.open_request_id ? (
        <div className="flex flex-col gap-3">
          <p className="text-muted">You already asked. You'll hear back in Intros.</p>
          <Link to="/intros" className="text-sm font-semibold text-blue hover:underline">
            Open Intros
          </Link>
        </div>
      ) : !p.can_request ? (
        <p role="alert" className="rounded-2xl border border-line bg-raised p-4">
          {p.blocked_reason}
        </p>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            send.mutate();
          }}
        >
          <label className="flex flex-col gap-2">
            <span>
              Why do you want to meet {p.target.display_name}?
              {p.via && ` ${p.via.display_name} reads this first.`}
            </span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
              rows={4}
              placeholder="One or two lines on what you'd like to talk about."
              className="rounded-xl border border-line bg-raised p-3 placeholder:text-muted"
            />
            <span className="text-right text-sm text-muted">
              {reason.trim().length < 10 ? "At least 10 characters · " : ""}
              {reason.trim().length}/500
            </span>
          </label>
          {send.isError && <ErrorState error={send.error} />}
          <PrimaryButton
            type="submit"
            disabled={reason.trim().length < 10 || send.isPending}
            className="min-h-14"
          >
            {send.isPending ? "Sending…" : "Send request"}
          </PrimaryButton>
        </form>
      )}
    </div>
  );
}
