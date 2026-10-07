import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, ApiError, type MemberSummary, memberStore, tokenStore, unwrap } from "./api/client";

type Auth = {
  token: string | null;
  member: MemberSummary | null;
  isDemo: boolean;
  loading: boolean;
  login: (persona: string) => Promise<MemberSummary>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<Auth | null>(null);

/** Forget everything the previous person saw: in-memory queries and the offline cache. */
async function forgetData(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.clear();
  try {
    if ("caches" in window) await caches.delete("circuit-api");
  } catch {
    // Cache Storage can be unavailable (private mode); nothing to clear then.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(() => tokenStore.get());
  const [saved, setSaved] = useState(() => memberStore.get());

  const me = useQuery({
    queryKey: ["auth", "me", token],
    queryFn: () => unwrap(api.GET("/api/auth/me")),
    enabled: token !== null,
    retry: (count, error) => !(error instanceof ApiError && error.status === 401) && count < 1,
  });

  const logout = useCallback(async () => {
    tokenStore.clear();
    setToken(null);
    setSaved(null);
    await forgetData(queryClient);
  }, [queryClient]);

  // A token the API no longer accepts (expired, or the seed was reset): sign out.
  const expired = me.error instanceof ApiError && me.error.status === 401;
  useEffect(() => {
    if (expired) void logout();
  }, [expired, logout]);

  // Keep the saved summary fresh (e.g. after an admin changes your level).
  const fresh = me.data?.member ?? null;
  const freshDemo = me.data?.is_demo ?? false;
  useEffect(() => {
    if (fresh) {
      const next = { member: fresh, isDemo: freshDemo };
      memberStore.set(next);
      setSaved(next);
    }
  }, [fresh, freshDemo]);

  const login = useCallback(
    async (persona: string) => {
      const out = await unwrap(api.POST("/api/auth/demo/login", { body: { persona } }));
      await forgetData(queryClient);
      tokenStore.set(out.access_token);
      const next = { member: out.member, isDemo: true }; // only demo logins exist so far
      memberStore.set(next);
      setSaved(next);
      setToken(out.access_token);
      return out.member;
    },
    [queryClient],
  );

  const value = useMemo<Auth>(
    () => ({
      token,
      // The server's answer, or the saved summary while it loads or when offline.
      member: token ? (fresh ?? saved?.member ?? null) : null,
      isDemo: token ? (me.data?.is_demo ?? saved?.isDemo ?? false) : false,
      loading: token !== null && me.isPending && saved === null,
      login,
      logout,
    }),
    [token, fresh, saved, me.data?.is_demo, me.isPending, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used inside <AuthProvider>");
  return auth;
}
