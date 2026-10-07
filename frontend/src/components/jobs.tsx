import type { Schemas } from "../api/client";
import { Pill } from "./ui";

export type ApplicationStatus = Schemas["ApplicationOut"]["status"];

const STATUS: Record<ApplicationStatus, { label: string; tone: "green" | "blue" | "neutral" }> = {
  submitted: { label: "Applied", tone: "neutral" },
  shortlisted: { label: "Shortlisted", tone: "blue" },
  hired: { label: "Hired", tone: "green" },
  rejected: { label: "Not selected", tone: "neutral" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};

export function StatusPill({ status }: { status: ApplicationStatus }) {
  const s = STATUS[status];
  return <Pill tone={s.tone}>{s.label}</Pill>;
}

export const JOB_TYPE: Record<Schemas["JobOut"]["type"], string> = {
  internship: "Internship",
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
};

export function pay(job: { paid: boolean; compensation?: string | null }) {
  return job.compensation ?? (job.paid ? "Paid" : "Unpaid");
}
