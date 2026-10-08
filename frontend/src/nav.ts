import type { Role } from "./api/client";

export type Tab = { to: string; label: string };

const T = {
  map: { to: "/map", label: "Map" },
  jobs: { to: "/jobs", label: "Jobs" },
  matches: { to: "/matches", label: "Matches" },
  circuits: { to: "/circuits", label: "Circuits" },
  intros: { to: "/intros", label: "Intros" },
  dashboard: { to: "/dashboard", label: "Dashboard" },
  me: { to: "/me", label: "Me" },
} satisfies Record<string, Tab>;

/** At most four tabs, chosen by role. The first one is the role's home. */
export function tabsFor(role: Role): Tab[] {
  switch (role) {
    case "student":
      return [T.map, T.jobs, T.matches, T.me];
    case "partner_admin":
      // Partner admins are often the mutual connection in a warm intro.
      return [T.dashboard, T.map, T.intros, T.me];
    default: // founder, mentor, investor
      return [T.matches, T.circuits, T.intros, T.me];
  }
}

export const ROLE_LABEL: Record<Role, string> = {
  student: "Student",
  founder: "Founder",
  mentor: "Mentor",
  investor: "Investor",
  partner_admin: "Partner admin",
};
