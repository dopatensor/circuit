import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router";
import { useAuth } from "./auth";
import { SkeletonBlock } from "./components/ds";
import { Page, Shell } from "./components/Shell";
import { HOME, discoverTabs } from "./nav";

// Each screen is its own chunk, so the first load stays small.
const Welcome = lazy(() => import("./screens/Welcome"));
const Home = lazy(() => import("./screens/Home"));
const Discover = lazy(() => import("./screens/Discover"));
const Me = lazy(() => import("./screens/Me"));
const MapScreen = lazy(() => import("./screens/MapScreen"));
const JobsScreen = lazy(() => import("./screens/Jobs"));
const JobPage = lazy(() => import("./screens/JobPage"));
const PostJob = lazy(() => import("./screens/PostJob"));
const StartupPage = lazy(() => import("./screens/StartupPage"));
const FindStartup = lazy(() => import("./screens/FindStartup"));
const Applicants = lazy(() => import("./screens/Applicants"));
const MatchesScreen = lazy(() => import("./screens/Matches"));
const CircuitsScreen = lazy(() => import("./screens/Circuits"));
const IntrosScreen = lazy(() => import("./screens/Intros"));
const DashboardScreen = lazy(() => import("./screens/Dashboard"));
const Onboarding = lazy(() => import("./screens/Onboarding"));
const DesignPage = lazy(() => import("./screens/Design"));
const Proof = lazy(() => import("./screens/Proof"));
const GitHubCallback = lazy(() => import("./screens/GitHubCallback"));
const Profile = lazy(() => import("./screens/Profile"));

// The component gallery: in dev, and in builds made with VITE_DESIGN_PAGE=1 (tests,
// demo deployments). Never in a normal production build.
const SHOW_DESIGN = import.meta.env.DEV || import.meta.env.VITE_DESIGN_PAGE === "1";

export default function App() {
  const { token, member, loading } = useAuth();
  const design = SHOW_DESIGN ? <Route path="/design" element={<DesignPage />} /> : null;

  if (!token) {
    return (
      <Routes>
        <Route path="/welcome" element={<Welcome />} />
        {design}
        <Route path="*" element={<Navigate to="/welcome" replace />} />
      </Routes>
    );
  }
  if (loading || !member) {
    return (
      <div className="mx-auto max-w-[640px] px-5">
        <Page>
          <SkeletonBlock className="h-9 w-2/3" />
          <SkeletonBlock className="h-40 w-full rounded-xl" />
        </Page>
      </div>
    );
  }

  const partner = member.role === "partner_admin";
  return (
    <Routes>
      {design}
      <Route element={<Shell />}>
        <Route path="/home" element={<Home />} />
        <Route path="/discover" element={<Navigate to={discoverTabs(member.role)[0].to} replace />} />
        {/* Discover's tabs: each its own URL (old links like /map keep working). */}
        <Route element={<Discover />}>
          {!partner && <Route path="/matches" element={<MatchesScreen />} />}
          <Route path="/jobs" element={<JobsScreen />} />
          <Route path="/startups" element={<FindStartup />} />
          <Route path="/map" element={<MapScreen />} />
        </Route>
        <Route path="/circuits" element={<CircuitsScreen />} />
        <Route path="/inbox" element={<IntrosScreen />} />
        <Route path="/intros" element={<Navigate to="/inbox" replace />} />
        {partner && <Route path="/dashboard" element={<DashboardScreen />} />}
        <Route path="/me" element={<Me />} />
        {!partner && <Route path="/me/profile" element={<Onboarding />} />}
        {member.role === "student" && <Route path="/me/proof" element={<Proof />} />}
        {member.role === "student" && <Route path="/me/github/callback" element={<GitHubCallback />} />}
        <Route path="/people/:memberId" element={<Profile />} />
        {member.role === "founder" && <Route path="/jobs/new" element={<PostJob />} />}
        <Route path="/jobs/:jobId" element={<JobPage />} />
        <Route path="/startups/:startupId" element={<StartupPage />} />
        <Route path="/startups/:startupId/applicants" element={<Applicants />} />
        {/* "/" (the installed app's start URL) and anything unknown: Home. */}
        <Route path="*" element={<Navigate to={HOME} replace />} />
      </Route>
    </Routes>
  );
}
