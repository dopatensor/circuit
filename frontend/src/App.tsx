import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router";
import { useAuth } from "./auth";
import { Page, Shell } from "./components/Shell";
import { Skeleton } from "./components/ui";
import { tabsFor } from "./nav";

// Each screen is its own chunk, so the first load stays small (the map and charts,
// coming in later phases, are the heavy ones).
const Welcome = lazy(() => import("./screens/Welcome"));
const Me = lazy(() => import("./screens/Me"));
const screens = (name: keyof typeof import("./screens/placeholders")) =>
  lazy(() => import("./screens/placeholders").then((m) => ({ default: m[name] })));
const MapScreen = lazy(() => import("./screens/MapScreen"));
const JobsScreen = lazy(() => import("./screens/Jobs"));
const JobPage = lazy(() => import("./screens/JobPage"));
const StartupPage = lazy(() => import("./screens/StartupPage"));
const FindStartup = lazy(() => import("./screens/FindStartup"));
const Applicants = lazy(() => import("./screens/Applicants"));
const MatchesScreen = lazy(() => import("./screens/Matches"));
const CircuitsScreen = screens("CircuitsScreen");
const IntrosScreen = screens("IntrosScreen");
const DashboardScreen = screens("DashboardScreen");

export default function App() {
  const { token, member, loading } = useAuth();

  if (!token) {
    return (
      <Routes>
        <Route path="/welcome" element={<Welcome />} />
        <Route path="*" element={<Navigate to="/welcome" replace />} />
      </Routes>
    );
  }
  if (loading || !member) {
    return (
      <div className="mx-auto max-w-[720px] px-4">
        <Page>
          <Skeleton />
        </Page>
      </div>
    );
  }

  const home = tabsFor(member.role)[0].to;
  const allowed = new Set(tabsFor(member.role).map((t) => t.to));
  const tab = (path: string, element: React.ReactNode) =>
    allowed.has(path) ? <Route path={path} element={element} /> : null;

  return (
    <Routes>
      <Route element={<Shell />}>
        {tab("/map", <MapScreen />)}
        {tab("/jobs", <JobsScreen />)}
        {tab("/matches", <MatchesScreen />)}
        {tab("/circuits", <CircuitsScreen />)}
        {tab("/intros", <IntrosScreen />)}
        {tab("/dashboard", <DashboardScreen />)}
        <Route path="/me" element={<Me />} />
        {/* Pages reached from a tab (or a link), open to every signed-in role. */}
        <Route path="/jobs/:jobId" element={<JobPage />} />
        <Route path="/startups" element={<FindStartup />} />
        <Route path="/startups/:startupId" element={<StartupPage />} />
        <Route path="/startups/:startupId/applicants" element={<Applicants />} />
        {/* "/" (the installed app's start URL) and anything unknown: your main tab. */}
        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  );
}
