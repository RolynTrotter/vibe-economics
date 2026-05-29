// Tiny fetch wrapper pointed at the backend. In dev, Vite proxies /api to the
// FastAPI server; in other setups set VITE_API_BASE to the backend origin.
const BASE = import.meta.env.VITE_API_BASE || "";

export async function api(path, params) {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
        )
      ).toString()
    : "";
  const res = await fetch(`${BASE}${path}${qs}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}
