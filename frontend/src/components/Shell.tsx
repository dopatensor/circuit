import { type ReactNode, Suspense } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth";
import { ROLE_LABEL, tabsFor } from "../nav";
import { InstallPrompt } from "../pwa/InstallPrompt";
import { UpdateBar } from "../pwa/UpdateBar";
import { Avatar, Skeleton } from "./ui";

// The map and the dashboard use the full width; everything else sits in a centred
// column of at most 720px.
const WIDE = ["/map", "/dashboard"];

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2 text-xl font-semibold tracking-tight">
      <span aria-hidden="true" className="size-2.5 rounded-full bg-blue shadow-glow-blue" />
      Circuit
    </span>
  );
}

function SideLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative flex min-h-11 items-center rounded-xl px-3 text-base transition-colors ${
          isActive
            ? "bg-raised font-semibold text-fg before:absolute before:inset-y-2.5 before:left-0 before:w-0.5 before:rounded-full before:bg-blue"
            : "text-muted hover:bg-surface hover:text-fg"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

function TabLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative flex min-h-14 flex-1 items-center justify-center text-sm transition-colors ${
          isActive
            ? "font-semibold text-blue after:absolute after:top-0 after:h-0.5 after:w-8 after:rounded-full after:bg-blue after:shadow-glow-blue"
            : "text-muted"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export function Shell() {
  const { member } = useAuth();
  const { pathname } = useLocation();
  const tabs = member ? tabsFor(member.role) : [];
  const wide = WIDE.some((p) => pathname.startsWith(p));

  return (
    <div className="flex min-h-dvh">
      {/* Laptops and tablets: a slim sidebar with the same tabs, and who you are. */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-8 border-r border-line px-4 pt-[max(1.75rem,env(safe-area-inset-top))] pb-5 md:flex">
        <div className="px-3">
          <Wordmark />
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {tabs.map((t) => (
            <SideLink key={t.to} {...t} />
          ))}
        </nav>
        {member && (
          <NavLink
            to="/me"
            className="mt-auto flex items-center gap-3 rounded-xl p-2 hover:bg-surface"
          >
            <Avatar name={member.display_name} size="sm" />
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-semibold">{member.display_name}</span>
              <span className="truncate text-sm text-muted">{ROLE_LABEL[member.role]}</span>
            </span>
          </NavLink>
        )}
      </aside>

      <main
        className={`pt-safe min-w-0 flex-1 pb-[calc(6rem+env(safe-area-inset-bottom))] md:pb-12 ${
          wide ? "w-full px-4 md:px-10" : "mx-auto w-full max-w-[720px] px-4 md:px-8"
        }`}
      >
        <Suspense
          fallback={
            <Page>
              <Skeleton />
            </Page>
          }
        >
          <Outlet />
        </Suspense>
      </main>

      {/* Phones: bars and the tab bar at the bottom, within thumb reach. */}
      <div className="fixed inset-x-0 bottom-0 z-20 flex flex-col md:inset-x-auto md:right-6 md:bottom-6 md:w-96 md:gap-2">
        <InstallPrompt />
        <UpdateBar />
        <nav
          aria-label="Main"
          className="pb-safe flex border-t border-line bg-black/90 backdrop-blur md:hidden"
        >
          {tabs.map((t) => (
            <TabLink key={t.to} {...t} />
          ))}
        </nav>
      </div>
    </div>
  );
}

/** Standard spacing for a screen. */
export function Page({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-6 py-6 md:py-10">{children}</div>;
}
