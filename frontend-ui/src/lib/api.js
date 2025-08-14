const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export async function planTrip(payload) {
  const r = await fetch(`${BASE}/api/plan-trip/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const ct = r.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await r.json() : await r.text();

  if (!r.ok) {
    const err = new Error("Request failed");
    err.status = r.status;
    err.body = body;
    throw err;
  }
  return body;
}

export async function renderLogbookSVG(payload) {
  const r = await fetch(`${BASE}/api/logbook/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`renderLogbook failed: ${r.status}`);
  return await r.text();
}
