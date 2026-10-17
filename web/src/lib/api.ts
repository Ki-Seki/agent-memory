// Talking to `mem ui`. The page arrives with its token in the address (#t=…); it moves to sessionStorage
// so the address can carry the route instead.
const KEY = "mem-ui-token";

function takeToken(): string {
  const m = location.hash.match(/[#&]t=([\w-]+)/);
  if (m) {
    sessionStorage.setItem(KEY, m[1]);
    const rest = location.hash.replace(/[#&]t=[\w-]+/, "").replace(/^#?&?/, "");
    history.replaceState(null, "", location.pathname + location.search + (rest ? `#${rest}` : ""));
  }
  return sessionStorage.getItem(KEY) || "";
}
export const token = takeToken();

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Mem-Token": token, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError((data as { error?: string }).error || `${r.status} ${r.statusText}`, r.status);
  return data as T;
}
