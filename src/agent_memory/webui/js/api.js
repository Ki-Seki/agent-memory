// Talking to `mem ui`. The page arrives with its token in the address (#t=…); it moves to sessionStorage
// so the address can carry the route instead. The online demo swaps in its own transport.
const KEY = "mem-ui-token";

function takeToken() {
  try {
    const m = location.hash.match(/[#&]t=([\w-]+)/);
    if (m) {
      sessionStorage.setItem(KEY, m[1]);
      const rest = location.hash.replace(/[#&]t=[\w-]+/, "").replace(/^#?&?/, "");
      history.replaceState(null, "", location.pathname + location.search + (rest ? `#${rest}` : ""));
    }
    return sessionStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}
export let token = takeToken();

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function http(path, body) {
  const r = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Mem-Token": token, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(data.error || `${r.status} ${r.statusText}`, r.status);
  return data;
}

let transport = http;
/** Replace the server with something else that answers the same calls, such as the demo's data. */
export function useTransport(fn) { transport = fn; token = "demo"; }

export const api = (path, body) => transport(path, body);
