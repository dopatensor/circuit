import { type ReactNode, Suspense } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth";
import { tabsFor } from "../nav";
import { InstallPrompt } from "../pwa/InstallPrompt";
import { UpdateBar } from "../pwa/UpdateBar";
import { Skeleton } from "./ui";

// The map and the dashboard use the full width; everything else sits in a centred
// column of at most 720px.
const WIDE = ["/map", "/dashboard"];

function TabLink({ to, label, vertical }: { to: string; label: string; vertical?: boolean }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          "flex min-h-11 items-center transition-colors",
          vertical
            ? "rounded-lg px-3 text-base"
            : "flex-1 flex-col justify-center border-t-2 text-sm",
          isActive
            ? `font-semibold text-fg ${vertical ? "bg-surface" : "border-fg"}`
            : `text-muted hover:text-fg ${vertical ? "" : "border-transparent"}`,
        ].join(" ")
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
      {/* Desktop and tablet: a slim sidebar with the same tabs. */}
      <aside className="sticky top-0 hidden h-dvh w-52 shrink-0 flex-col gap-6 border-r border-line px-4 pt-[max(1.5rem,env(safe-area-inset-top))] pb-6 md:flex">
        <span className="px-3 text-base font-semibold tracking-tight">Circuit</span>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {tabs.map((t) => (
            <TabLink key={t.to} {...t} vertical />
          ))}
        </nav>
      </aside>

      <main
        className={`pt-safe min-w-0 flex-1 pb-[calc(5rem+env(safe-area-inset-bottom))] md:pb-10 ${
          wide ? "w-full px-4 md:px-8" : "mx-auto w-full max-w-[720px] px-4 md:px-8"
        }`}
      >
        <Suspense fallback={<Page><Skeleton /></Page>}>
          <Outlet />
        </Suspense>
      </main>

      {/* Phones: bars and the tab bar at the bottom, within thumb reach. */}
      <div className="fixed inset-x-0 bottom-0 z-20 flex flex-col md:inset-x-auto md:right-6 md:bottom-6 md:w-96 md:gap-2">
        <InstallPrompt />
        <UpdateBar />
        <nav
          aria-label="Main"
          className="pb-safe flex border-t border-line bg-bg md:hidden"
        >
          {tabs.map((t) => (
            <TabLink key={t.to} {...t} />
          ))}
        </nav>
      </div>
    </div>
  );
}

/** Standard spacing for a screen in the centred column. */
export function Page({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-6 py-6 md:py-10">{children}</div>;
}
