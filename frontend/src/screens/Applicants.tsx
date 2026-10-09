import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api, type Schemas, unwrap } from "../api/client";
import { useCapabilities } from "../api/hooks";
import { StatusPill } from "../components/jobs";
import { Page } from "../components/Shell";
import { Avatar, Empty, ErrorState, Muted, Pill, Skeleton, Title } from "../components/ui";

type Applicant = Schemas["ApplicantOut"];
type Status = Schemas["ApplicationStatusIn"]["status"];

/** Founders: applicants ranked by skill match (never by college), with one tap to
 *  shortlist, hire or pass. */
export default function Applicants() {
  const { startupId = "" } = useParams();
  const path = { params: { path: { startup_id: startupId } } };
  const startup = useQuery({
    queryKey: ["startup", startupId],
    queryFn: () => unwrap(api.GET("/api/startups/{startup_id}", path)),
  });
  const applicants = useQuery({
    queryKey: ["startup", startupId, "applicants"],
    queryFn: () => unwrap(api.GET("/api/startups/{startup_id}/applicants", path)),
  });

  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Link to={`/startups/${startupId}`} className="text-sm text-fg underline underline-offset-2 hover:text-fg2">
          {startup.data?.name ?? "Startup"}
        </Link>
        <Title>Applicants</Title>
        <Muted>Ranked by how well their skills match the job.</Muted>
      </div>
      {applicants.isPending ? (
        <Skeleton lines={3} className="h-40" />
      ) : applicants.isError ? (
        <ErrorState error={applicants.error} retry={applicants.refetch} />
      ) : applicants.data.length === 0 ? (
        <Empty>No applications yet. They'll appear here as students apply.</Empty>
      ) : (
        <ul className="flex flex-col gap-3">
          {applicants.data.map((a) => (
            <ApplicantCard key={a.application_id} applicant={a} startupId={startupId} />
          ))}
        </ul>
      )}
    </Page>
  );
}

const ACTIONS: [Status, string][] = [
  ["shortlisted", "Shortlist"],
  ["hired", "Hire"],
  ["rejected", "Not a fit"],
];

function ApplicantCard({ applicant: a, startupId }: { applicant: Applicant; startupId: string }) {
  const caps = useCapabilities();
  const queryClient = useQueryClient();
  const matched = new Set(a.match.matched);
  const update = useMutation({
    mutationFn: (status: Status) =>
      unwrap(
        api.PATCH("/api/applications/{application_id}", {
          params: { path: { application_id: a.application_id } },
          body: { status },
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["startup", startupId, "applicants"] }),
  });
  const final = a.status === "withdrawn";

  return (
    <li className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-5">
      <div className="flex items-start gap-3">
        <Avatar name={a.member.display_name} />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-semibold">{a.member.display_name}</span>
          <span className="truncate text-sm text-muted">{a.job_title}</span>
        </div>
        <div className="flex shrink-0 flex-col items-end">
          <span className={`num text-xl`}>
            {a.match.score}%
          </span>
          <span className="text-sm text-muted">match</span>
        </div>
      </div>
      <ul className="flex flex-wrap gap-2" aria-label="Skills">
        {a.skills.map((s) => (
          <li key={s.capability_id}>
            <Pill tone={matched.has(s.capability_id) ? "green" : "neutral"}>
              {caps.name(s.capability_id)}
            </Pill>
          </li>
        ))}
      </ul>
      {a.note && <p className="border-l-2 border-line pl-3 text-muted">“{a.note}”</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusPill status={a.status} />
        {!final && (
          <div className="flex gap-2">
            {ACTIONS.filter(([s]) => s !== a.status).map(([status, label]) => (
              <button
                key={status}
                disabled={update.isPending}
                onClick={() => update.mutate(status)}
                className={`min-h-11 rounded-lg border px-4 text-sm font-semibold disabled:opacity-40 ${
                  status === "shortlisted"
                    ? "border-line2 text-fg hover:border-fg2"
                    : "border-line hover:border-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      {update.isError && <ErrorState error={update.error} />}
    </li>
  );
}
