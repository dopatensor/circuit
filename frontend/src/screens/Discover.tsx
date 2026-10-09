import { Outlet } from "react-router";
import { useAuth } from "../auth";
import { TabLinks } from "../components/ds";
import { discoverTabs } from "../nav";

/** Discover: tabs over the browse screens (matches, jobs, startups, the map). Each tab is
 *  its own URL, so links and the back button work. */
export default function Discover() {
  const { member } = useAuth();
  if (!member) return null;
  return (
    <div className="pt-4 md:pt-8">
      <TabLinks label="Discover" tabs={discoverTabs(member.role)} />
      <Outlet />
    </div>
  );
}

