const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export async function planTrip(payload) {
  const r = await fetch(`${BASE}/api/plan-trip/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`planTrip failed: ${r.status}`);
  return r.json();
}

export async function renderLogbookSVG(payload) {
  const res = await fetch(`${BASE}/api/logbook/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`renderLogbook failed: ${res.status}`);
  return await res.text(); // SVG string
}
