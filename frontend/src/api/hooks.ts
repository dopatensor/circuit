import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";

/** The fixed capability list (id -> display name). Loaded once per session. */
export function useCapabilities() {
  const q = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => unwrap(api.GET("/api/capabilities")),
    staleTime: Infinity,
  });
  const names = new Map((q.data ?? []).map((c) => [c.id, c.name]));
  return { ...q, name: (id: string) => names.get(id) ?? id.replace(/_/g, " ") };
}

/** Your own profile (includes the startups you're part of). */
export function useMyProfile(enabled = true) {
  return useQuery({
    queryKey: ["members", "me"],
    queryFn: () => unwrap(api.GET("/api/members/me")),
    enabled,
  });
}
