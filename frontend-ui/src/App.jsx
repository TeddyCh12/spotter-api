import { useEffect, useMemo, useState } from "react";
import MapView from "./components/MapView";
import { planTrip, renderLogbookSVG } from "./lib/api";

export default function App() {
  const [form, setForm] = useState({
    current_location: "",
    pickup_location: "",
    dropoff_location: "",
    current_cycle_used_hours: "",
    // start_time_iso: "",
  });

  const [touched, setTouched] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [trip, setTrip] = useState(null);
  const [logbooks, setLogbooks] = useState({}); // date -> svg
  const [logbooksLoading, setLogbooksLoading] = useState(false);
  const [triedSubmit, setTriedSubmit] = useState(false);
  const [apiError, setApiError] = useState(null);

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  };

  const onBlur = (e) => {
    setTouched((t) => ({ ...t, [e.target.name]: true }));
  };

  const validate = (f) => {
    const next = {};
    if (!f.current_location.trim()) next.current_location = "Required";
    if (!f.pickup_location.trim()) next.pickup_location = "Required";
    if (!f.dropoff_location.trim()) next.dropoff_location = "Required";
    if (f.current_cycle_used_hours === "") {
      next.current_cycle_used_hours = "Required";
    } else if (isNaN(Number(f.current_cycle_used_hours)) || Number(f.current_cycle_used_hours) < 0) {
      next.current_cycle_used_hours = "Enter a non-negative number";
    }
    return next;
  };

  const isValid = useMemo(() => Object.keys(validate(form)).length === 0, [form]);

const onSubmit = async (e) => {
  e.preventDefault();
  setTriedSubmit(true);
  setApiError(null);
  setErrors({});

  const v = validate(form);
  setErrors(v);
  setTouched({
    current_location: true,
    pickup_location: true,
    dropoff_location: true,
    current_cycle_used_hours: true,
  });
  if (Object.keys(v).length) return;

  setLoading(true);
  setTrip(null);
  setLogbooks({});
  try {
    const data = await planTrip({
      current_location: form.current_location.trim(),
      pickup_location: form.pickup_location.trim(),
      dropoff_location: form.dropoff_location.trim(),
      current_cycle_used_hours: Number(form.current_cycle_used_hours),
      // start_time_iso: form.start_time_iso,
    });
    setTrip(data);
  } catch (err) {
    if (err.status === 400 && err.body && typeof err.body === "object") {
      const serverErrs = {};
      for (const [k, vMsgs] of Object.entries(err.body)) {
        if (Array.isArray(vMsgs) && vMsgs.length) serverErrs[k] = vMsgs[0];
      }
      setErrors((prev) => ({ ...prev, ...serverErrs }));
      setTouched((t) => ({ ...t, ...Object.fromEntries(Object.keys(serverErrs).map(k => [k, true])) }));
    } else {
      const detail = err?.body?.detail || err.message || "Something went wrong. Please try again.";
      setApiError(detail);
    }
  } finally {
    setLoading(false);
  }
};

  useEffect(() => {
    const run = async () => {
      if (!trip?.days?.length) return;
      setLogbooksLoading(true);
      try {
        const entries = await Promise.all(
          trip.days.map(async (d) => {
            const svg = await renderLogbookSVG({
              date: d.date,
              segments: d.segments,
              labels: d.labels ?? [],
            });
            return [d.date, svg];
          })
        );
        setLogbooks(Object.fromEntries(entries));
      } catch (err) {
        console.error(err);
      } finally {
        setLogbooksLoading(false);
      }
    };
    run();
  }, [trip]);

  // helper to style inputs per field
  const inputClass = (name) =>
    `mt-1 w-full h-9 text-sm rounded-md border px-3 outline-none focus:ring-2 focus:ring-black/70 transition ${
      touched[name] && errors[name] ? "border-red-400" : "border-gray-300"
    }`;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="py-10 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Trip Planner</h1>
        <p className="text-gray-500 mt-2">Plan a trip</p>
      </header>

      <main className="max-w-5xl mx-auto px-4 pb-16">
        <form
          onSubmit={onSubmit}
          className="relative bg-white shadow rounded-2xl p-6 space-y-4 max-w-md mx-auto"
          autoComplete="off"
        >
          <div>
            <label className="block text-sm font-medium">Current location</label>
            <input
              name="current_location"
              value={form.current_location}
              onChange={onChange}
              onBlur={onBlur}
              aria-invalid={Boolean(touched.current_location && errors.current_location)}
              className={inputClass("current_location")}
            />
            {touched.current_location && errors.current_location && (
              <p className="text-red-500 text-xs mt-1">{errors.current_location}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium">Pickup location</label>
            <input
              name="pickup_location"
              value={form.pickup_location}
              onChange={onChange}
              onBlur={onBlur}
              className={inputClass("pickup_location")}
            />
            {touched.pickup_location && errors.pickup_location && (
              <p className="text-red-500 text-xs mt-1">{errors.pickup_location}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium">Dropoff location</label>
            <input
              name="dropoff_location"
              value={form.dropoff_location}
              onChange={onChange}
              onBlur={onBlur}
              className={inputClass("dropoff_location")}
            />
            {touched.dropoff_location && errors.dropoff_location && (
              <p className="text-red-500 text-xs mt-1">{errors.dropoff_location}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium">Current cycle used (hrs)</label>
            <input
              name="current_cycle_used_hours"
              type="number"
              inputMode="decimal"
              step="0.1"
              min="0"
              value={form.current_cycle_used_hours}
              onChange={onChange}
              onBlur={onBlur}
              className={inputClass("current_cycle_used_hours")}
            />
            {touched.current_cycle_used_hours && errors.current_cycle_used_hours && (
              <p className="text-red-500 text-xs mt-1">{errors.current_cycle_used_hours}</p>
            )}
          </div>

          {/* Optional start_time_iso
          <div className="md:col-span-2">
            <label className="block text-sm font-medium">Start time (ISO)</label>
            <input
              name="start_time_iso"
              value={form.start_time_iso}
              onChange={onChange}
              onBlur={onBlur}
             className="mt-1 w-full h-10 text-sm rounded-md border px-3 outline-none focus:ring-2 focus:ring-black/70 transition border-gray-300"
              placeholder="YYYY-MM-DDTHH:mm:ss±HH:MM"
            />
          </div>
          */}

          {/* Primary action centered */}
          <div className="mt-4 flex flex-col items-center gap-2">
            <button
              className="px-5 py-2.5 rounded-md bg-black text-white"
              disabled={loading}
            >
              {loading ? "Planning..." : "Plan Trip"}
            </button>

            {apiError && (
              <p className="text-sm text-red-600">{apiError}</p>
            )}

            {triedSubmit && !isValid && (
              <p className="text-sm text-red-600">Fill all required fields</p>
            )}
          </div>

          {/* Reset bottom-right */}
          <button
            type="button"
            className="absolute bottom-4 right-4 px-3 py-1.5 text-sm rounded-md border border-gray-300"
            onClick={() => {
              setForm({
                current_location: "",
                pickup_location: "",
                dropoff_location: "",
                current_cycle_used_hours: "",
              });
              setErrors({});
              setTouched({});
              setTrip(null);
              setLogbooks({});
              setTriedSubmit(false);
            }}
          >
            Reset
          </button>
        </form>

        {trip && (
          <>
            <section className="mt-8">
              <div className="bg-white shadow rounded-2xl p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Route</h2>
                  <div className="text-sm text-gray-600">
                    {trip.summary.distance_miles} mi • {trip.summary.drive_hours} hrs
                    {trip.summary.cycle_exceeded && (
                      <span className="ml-2 inline-block px-2 py-0.5 rounded bg-red-50 text-red-700 text-xs">
                        Cycle exceeded
                      </span>
                    )}
                  </div>
                </div>
                <div className="mt-3">
                  <MapView polyline={trip.polyline} places={trip.places} stops={trip.stops} />
                </div>
              </div>
            </section>

            <section className="mt-8">
              <div className="bg-white shadow rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold">Daily Log Sheets</h2>
                  <div className="text-sm text-gray-600">
                    {trip.summary.distance_miles} mi • {trip.summary.drive_hours} hrs
                    {trip.summary.cycle_exceeded && (
                      <span className="ml-2 inline-block px-2 py-0.5 rounded bg-red-50 text-red-700 text-xs">
                        Cycle exceeded
                      </span>
                    )}
                  </div>
                </div>
                  
                <div className="mt-2 space-y-6">
                  {trip.days.map((d) => (
                    <div key={d.date} className="w-full">
                      <div className="text-sm font-medium mb-2">{d.date}</div>
                  
                      {logbooksLoading && !logbooks[d.date] ? (
                        <div className="h-56 bg-gray-100 animate-pulse rounded-md" />
                      ) : logbooks[d.date] ? (
                        <img
                          alt={`Logbook ${d.date}`}
                          className="w-full h-auto rounded-md"
                          src={`data:image/svg+xml;utf8,${encodeURIComponent(logbooks[d.date])}`}
                        />
                      ) : (
                        <div className="text-sm text-gray-500">Could not load.</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
