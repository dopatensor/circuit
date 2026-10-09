import { type ReactNode, Suspense, lazy, useState } from "react";
import { Link, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth";
import { HOME, NAV, type NavItem, ROLE_LABEL, discoverTabs, mainAction } from "../nav";
import { InstallPrompt } from "../pwa/InstallPrompt";
import { UpdateBar } from "../pwa/UpdateBar";
import { Avatar, Icon, Logo, SkeletonBlock, buttonClass } from "./ds";
import { PostSheet } from "./PostSheet";

// The right rail (profile strength, people, jobs) only exists on wide screens, so its
// code loads on its own.
const RightRail = lazy(() => import("./RightRail"));

// The map and the dashboard use the full width and have no right rail.
const WIDE = ["/map", "/dashboard"];

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2 text-lg font-semibold tracking-[-0.01em]">
      <Logo />
      Circuit
    </span>
  );
}

/** Which nav item a path belongs to (Discover covers its tabs; Inbox covers intros). */
function useActive() {
  const { pathname } = useLocation();
  const { member } = useAuth();
  const discover = member ? discoverTabs(member.role).map((t) => t.to) : [];
  return (item: NavItem) => {
    if (item.to === "/discover")
      return pathname !== "/jobs/new" && discover.some((p) => pathname === p || pathname.startsWith(`${p}/`));
    if (item.to === "/inbox") return pathname.startsWith("/inbox") || pathname.startsWith("/intros");
    return pathname === item.to || pathname.startsWith(`${item.to}/`);
  };
}

function SideItem({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      to={item.to}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-11 items-center gap-3 rounded-lg px-3 text-[15px] font-semibold transition-colors ${
        active ? "bg-raised text-fg" : "text-fg2 hover:bg-raised/70 hover:text-fg"
      }`}
    >
      <Icon name={item.icon} />
      {item.label}
    </Link>
  );
}

function TabItem({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      to={item.to}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-14 flex-col items-center justify-center gap-1 text-[11px] leading-3 font-semibold transition-colors ${
        active ? "text-fg" : "text-muted"
      }`}
    >
      <Icon name={item.icon} size={22} />
      {item.label}
    </Link>
  );
}

export function Shell() {
  const { member } = useAuth();
  const { pathname } = useLocation();
  const isActive = useActive();
  const [posting, setPosting] = useState(false);
  if (!member) return null;
  const action = mainAction(member.role);
  const wide = WIDE.some((p) => pathname.startsWith(p));
  const meActive = pathname === "/me" || pathname.startsWith("/me/");

  const actionDesktop =
    action.kind === "link" ? (
      <Link to={action.to} className={buttonClass("primary", "md", "w-full")}>
        <Icon name={action.icon} size={18} />
        {action.long}
      </Link>
    ) : (
      <button type="button" onClick={() => setPosting(true)} className={buttonClass("primary", "md", "w-full")}>
        <Icon name={action.icon} size={18} />
        {action.long}
      </button>
    );

  const centre = (
    <span className="flex size-11 items-center justify-center rounded-[10px] bg-accent text-ink transition-transform duration-150 active:scale-95">
      <Icon name={action.icon} size={22} />
    </span>
  );
  const actionPhone =
    action.kind === "link" ? (
      <Link to={action.to} className="flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] leading-3 font-semibold text-fg">
        {centre}
        {action.label}
      </Link>
    ) : (
      <button
        type="button"
        onClick={() => setPosting(true)}
        className="flex min-h-14 cursor-pointer flex-col items-center justify-center gap-0.5 text-[11px] leading-3 font-semibold text-fg"
      >
        {centre}
        {action.label}
      </button>
    );

  return (
    <div className="flex min-h-dvh">
      {/* Tablets and laptops: a sidebar with the same places, the main action, and you. */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-line px-3 pt-[max(1.25rem,env(safe-area-inset-top))] pb-3 md:flex">
        <Link to={HOME} className="mb-6 px-3">
          <Wordmark />
        </Link>
        <nav aria-label="Main" className="flex flex-col gap-0.5">
          {NAV.map((item) => (
            <SideItem key={item.to} item={item} active={isActive(item)} />
          ))}
          <SideItem item={{ to: "/me", label: "Me", icon: "user" }} active={meActive} />
          <div className="mt-4">{actionDesktop}</div>
        </nav>
        <Link
          to="/me"
          className="mt-auto flex items-center gap-3 rounded-lg border-t border-line p-3 pt-4 hover:bg-raised/70"
        >
          <Avatar name={member.display_name} size={32} />
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-semibold">{member.display_name}</span>
            <span className="truncate text-xs text-muted">{ROLE_LABEL[member.role]}</span>
          </span>
        </Link>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Phones: a slim top bar. Me is your avatar, top right. */}
        <header className="pt-safe sticky top-0 z-20 border-b border-line bg-bg md:hidden">
          <div className="flex h-14 items-center gap-1 pr-2 pl-5">
            <Link to={HOME} className="flex-1">
              <Wordmark />
            </Link>
            <Link
              to="/me"
              aria-label="Me"
              aria-current={meActive ? "page" : undefined}
              className="inline-flex size-11 items-center justify-center rounded-full"
            >
              <Avatar name={member.display_name} size={32} className={meActive ? "ring-2 ring-fg" : ""} />
            </Link>
          </div>
        </header>

        <div
          className={`mx-auto flex w-full gap-10 px-5 md:px-10 ${wide ? "" : "max-w-[1040px] justify-center"}`}
        >
          <main
            className={`min-w-0 flex-1 pb-[calc(6rem+env(safe-area-inset-bottom))] md:pb-16 ${
              wide ? "w-full" : "max-w-[640px]"
            }`}
          >
            <Suspense
              fallback={
                <Page>
                  <SkeletonBlock className="h-9 w-2/3" />
                  <SkeletonBlock className="h-40 w-full rounded-xl" />
                </Page>
              }
            >
              <Outlet />
            </Suspense>
          </main>
          {!wide && (
            <aside aria-label="For you" className="hidden w-[300px] shrink-0 py-10 xl:block">
              <div className="sticky top-10 flex flex-col gap-4">
                <Suspense fallback={<SkeletonBlock className="h-64 w-full rounded-xl" />}>
                  <RightRail />
                </Suspense>
              </div>
            </aside>
          )}
        </div>
      </div>

      {/* Phones: the bars and the tab bar at the bottom, within thumb reach. */}
      <div className="fixed inset-x-0 bottom-0 z-20 flex flex-col md:inset-x-auto md:right-6 md:bottom-6 md:w-96 md:gap-2">
        <InstallPrompt />
        <UpdateBar />
        <nav aria-label="Main" className="pb-safe grid grid-cols-5 border-t border-line bg-panel md:hidden">
          <TabItem item={NAV[0]} active={isActive(NAV[0])} />
          <TabItem item={NAV[1]} active={isActive(NAV[1])} />
          {actionPhone}
          <TabItem item={NAV[2]} active={isActive(NAV[2])} />
          <TabItem item={NAV[3]} active={isActive(NAV[3])} />
        </nav>
      </div>

      {action.kind === "post" && <PostSheet open={posting} onClose={() => setPosting(false)} />}
    </div>
  );
}

/** Standard spacing for a screen. */
export function Page({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-8 py-6 md:py-10">{children}</div>;
}

/** The top of a screen: a title and one plain sentence saying what it's for. */
export function PageHeader({ title, intro, children }: { title: ReactNode; intro?: ReactNode; children?: ReactNode }) {
  return (
    <header className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-[-0.015em]">{title}</h1>
      {intro && <p className="text-fg2">{intro}</p>}
      {children}
    </header>
  );
}
