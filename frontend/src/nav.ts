import type { Role } from "./api/client";
import type { IconName } from "./components/ds";

// Navigation (DESIGN.md §4). Everyone gets the same four places, so the app is learned
// once: Home · Discover · Circuits · Inbox, plus Me (your avatar). The centre button is
// the role's main action.

export type NavItem = { to: string; label: string; icon: IconName };

export const HOME = "/home";

export const NAV: NavItem[] = [
  { to: "/home", label: "Home", icon: "home" },
  { to: "/discover", label: "Discover", icon: "search" },
  { to: "/circuits", label: "Circuits", icon: "circuit" },
  { to: "/inbox", label: "Inbox", icon: "inbox" },
];

/** The centre action: a page to open, or (founders) a choice of what to post. */
export type MainAction =
  | { kind: "link"; to: string; label: string; long: string; icon: IconName }
  | { kind: "post"; label: string; long: string; icon: IconName };

export function mainAction(role: Role): MainAction {
  switch (role) {
    case "student":
      return { kind: "link", to: "/jobs", label: "Jobs", long: "Find jobs", icon: "briefcase" };
    case "founder":
      return { kind: "post", label: "Post", long: "Post a job or need", icon: "plus" };
    case "partner_admin":
      return { kind: "link", to: "/dashboard", label: "Gaps", long: "Ecosystem gaps", icon: "chart" };
    default: // mentor, investor
      return { kind: "link", to: "/me/profile", label: "Offer", long: "Offer help", icon: "hand" };
  }
}

/** Discover's tabs. Students start on the map (find startups near you); others on
 *  their matches. Partner admins have no matches of their own. */
export function discoverTabs(role: Role): { to: string; label: string }[] {
  const matches = { to: "/matches", label: "Matches" };
  const jobs = { to: "/jobs", label: "Jobs" };
  const startups = { to: "/startups", label: "Startups" };
  const map = { to: "/map", label: "Map" };
  if (role === "student") return [map, jobs, matches, startups];
  if (role === "partner_admin") return [map, startups, jobs];
  return [matches, jobs, startups, map];
}

export const ROLE_LABEL: Record<Role, string> = {
  student: "Student",
  founder: "Founder",
  mentor: "Mentor",
  investor: "Investor",
  partner_admin: "Partner admin",
};
