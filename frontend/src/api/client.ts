// The one way the app talks to the backend: a typed client generated from the API's
// OpenAPI spec (src/api/schema.d.ts, via `npm run gen:api`). No hand-written fetch.
import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type MemberSummary = Schemas["MemberSummary"];
export type Role = MemberSummary["role"];

const TOKEN_KEY = "circuit.token";
const MEMBER_KEY = "circuit.member";

// The token lives in localStorage so an installed app stays signed in. The service
// worker never sees or caches it (see vite.config.ts). Next to it we keep your own
// summary (name, role, level), so the app opens instantly and works offline; the
// server re-checks it whenever it's reachable.
export type SavedMember = { member: MemberSummary; isDemo: boolean };

export const memberStore = {
  get(): SavedMember | null {
    try {
      const raw = localStorage.getItem(MEMBER_KEY);
      return raw ? (JSON.parse(raw) as SavedMember) : null;
    } catch {
      return null;
    }
  },
  set(saved: SavedMember) {
    localStorage.setItem(MEMBER_KEY, JSON.stringify(saved));
  },
};

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(MEMBER_KEY);
  },
};

const withToken: Middleware = {
  onRequest({ request }) {
    const token = tokenStore.get();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: import.meta.env.VITE_API_URL ?? "" });
api.use(withToken);

/** An API failure with one plain sentence that can be shown as-is. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function sentenceFor(status: number, error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  // The API writes its refusals (busy weeks, levels, duplicates) to be shown as-is.
  if (typeof detail === "string" && status !== 500) return detail;
  if (status === 401) return "Your session ended. Please sign in again.";
  if (status === 403) return "You don't have access to this yet.";
  if (status === 404) return "We couldn't find that.";
  if (status === 422) return "Something in the form needs another look.";
  return "Something went wrong on our side. Please try again.";
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Await an api call: the data, or an ApiError with a plain sentence. */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  return (await withMeta(call)).data;
}

/** Like unwrap, plus when the server produced the data (older when served offline
 *  from the service worker's cache), for "Last updated <time>". */
export async function withMeta<T>(call: Promise<Result<T>>): Promise<{ data: T; servedAt: Date | null }> {
  let result: Result<T>;
  try {
    result = await call;
  } catch {
    throw new ApiError(0, "You're offline, or the server can't be reached right now.");
  }
  const { data, error, response } = result;
  if (error !== undefined || !response.ok) {
    throw new ApiError(response.status, sentenceFor(response.status, error));
  }
  const date = response.headers.get("date");
  return { data: data as T, servedAt: date ? new Date(date) : null };
}
