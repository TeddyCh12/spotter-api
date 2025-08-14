# Trip Planner (Django + React)

A full-stack app that takes trip details as inputs and outputs route instructions and ELD-style daily log sheets. Frontend is built with React (Vite) and MapLibre GL; backend is Django (REST) with HOS (Hours-of-Service) planning.

---

## Features

- **Inputs**: Current location, Pickup, Dropoff, Current Cycle Used (hrs), optional start time.
- **Outputs**:
  - Interactive map with route (polyline6) and pins for pickup/dropoff/breaks/fuel/overnights.
  - **Daily Log Sheets** rendered as SVG with OFF/SB/D/ON lanes.
- **HOS logic** (property-carrying, 70/8 cycle):
  - Max **11 hr driving** per duty day
  - **14 hr on-duty window**
  - **30-min break** required before **8 hr** of cumulative driving
  - **10-hr overnight OFF**
  - **+1 hr** pre-trip at start and **+1 hr** post-trip at end
- **Validation**:
  - Field-level 400 errors for invalid locations (e.g., misspelled states)
  - Friendly message for routing outages (5xx)
- **Nice touches**:
  - 5-minute quantization for clean hour alignment
  - Micro-segment cleanup to remove jitter/blips
  - Label stacking with priority (30-min break above Fuel)

---

## Tech Stack

- **Frontend**: React (Vite), MapLibre GL, Tailwind CSS
- **Backend**: Django, Django REST Framework, Gunicorn
- **Routing**: OSRM public demo (for light usage)
- **Geocoding**: Nominatim (with proper User-Agent and throttling)
- **Hosting**: Suitable for Vercel (frontend) + Render (backend)

---

## Project Structure

```
.
├── backend/
│   ├── manage.py
│   └── planning/
│       ├── views.py        # REST endpoints (/api/plan-trip/, /api/logbook/)
│       ├── hos.py          # Hours-of-Service planning
│       ├── logbook.py      # SVG rendering & segment normalization
│       └── routing.py      # Geocoding & routing helpers
└── frontend-ui/
    ├── src/
    │   ├── App.jsx
    │   ├── components/MapView.jsx
    │   └── lib/api.js
    └── index.html
```

---

## API

### `POST /api/plan-trip/`
**Request JSON**
```json
{
  "current_location": "Houston, TX",
  "pickup_location": "Austin, TX",
  "dropoff_location": "New York, NY",
  "current_cycle_used_hours": 62,
  "start_time_iso": "2025-08-14T08:00:00Z"
}
```

**Response JSON (abridged)**
```json
{
  "polyline": "encoded_polyline6_here",
  "summary": {
    "distance_miles": 1906.9,
    "drive_hours": 34.79,
    "cycle_used_hours": 68.79,
    "cycle_max_hours": 70.0,
    "cycle_exceeded": false
  },
  "places": { "current": {...}, "pickup": {...}, "dropoff": {...} },
  "stops": [
    { "type":"pickup_on_duty","at_iso":"...","duration_min":60 },
    { "type":"break_30min","at_iso":"...","duration_min":30 },
    { "type":"fuel_stop","at_iso":"...","duration_min":0 },
    { "type":"overnight_off","at_iso":"...","duration_min":600 },
    { "type":"dropoff_on_duty","at_iso":"...","duration_min":60 }
  ],
  "days": [
    {
      "date": "2025-08-14",
      "segments": [
        {"status":"ON","from":"08:00","to":"09:00"},
        {"status":"D","from":"09:00","to":"..."},
        {"status":"OFF","from":"...","to":"24:00"}
      ],
      "labels": [
        {"time":"09:00","text":"Pre-trip/TIV — Austin, TX"},
        {"time":"...","text":"30-min break"},
        {"time":"...","text":"Fuel stop"}
      ],
      "totals": {"OFF":..., "SB":..., "D":..., "ON":...}
    }
  ]
}
```

**Error shapes**
- **400** (field errors):
  ```json
  { "pickup_location": ["We couldn't find the pickup location. Try 'City, ST'."] }
  ```
- **502** (routing outage):
  ```json
  { "detail": "We couldn't compute a route between those locations. Please try again." }
  ```

### `POST /api/logbook/`
**Request JSON**
```json
{ "date":"2025-08-14", "segments":[{ "status":"D","from":"09:00","to":"13:30" }], "labels":[...] }
```
**Response**: SVG (as text)

---

## Frontend Usage

- `src/lib/api.js` reads `VITE_API_BASE` to reach the backend.
- `App.jsx` handles:
  - Form validation on submit (no pre-submit validation noise)
  - Posting to `/api/plan-trip/`
  - Rendering the map and requesting per-day SVGs via `/api/logbook/`
  - Displaying field-level errors and a global error if needed

**Environment (frontend)**
```
VITE_API_BASE=<backend origin, e.g., your Render service>
```
*(Use the backend origin only; no trailing slash.)*

---

## Backend Notes

- **HOS** (`planning/hos.py`)
  - Implements 11/14 limits, 8-hr break rule, 10-hr overnight, and 1-hr pre/post.
  - Default start at 08:00 if `start_time_iso` not provided.
  - All times rounded to 5-minute bins.

- **Logbook rendering** (`planning/logbook.py`)
  - `normalize_segments`: split across midnight, fill OFF gaps, merge, drop micro-segments, quantize 5 min.
  - `render_svg`: draws the grid and segments; stacks labels so the **30-min break** appears **above** **Fuel** at the same time or near-by times.

- **Routing & Geocoding** (`planning/routing.py`)
  - OSRM public demo for routing (light usage).
  - Nominatim for geocoding with a real User-Agent and a small delay between requests.
  - Returns polyline6 geometry, distance (m/mi), duration (s/hr).

---

## Running Locally

### Requirements
- Python 3.11+
- Node 18+

### Backend
```bash
cd backend
python -m venv .venv
. .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DJANGO_SECRET_KEY=dev-secret
export ALLOWED_HOSTS=localhost,127.0.0.1
export CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173
export CSRF_TRUSTED_ORIGINS=http://127.0.0.1:5173
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Frontend
```bash
cd frontend-ui
npm install
# Point to your local backend:
# VITE_API_BASE=http://127.0.0.1:8000
echo "VITE_API_BASE=http://127.0.0.1:8000" > .env
npm run dev
```

Open the frontend dev server in your browser and plan a test trip.

---

## Deploying

- **Frontend**: Build with Vite; set `VITE_API_BASE` to your backend origin; deploy to a static host.
- **Backend**: Deploy Django with Gunicorn on a managed host.
  - Env vars: `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`
  - Start command example: `gunicorn <project_name>.wsgi:application --bind 0.0.0.0:$PORT`

---

## Troubleshooting

- **CORS errors**: Ensure frontend origin is listed in `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`.
- **Field errors**: The API returns 400 with `{ field: ["message"] }`. Surface them inline.
- **Routing 5xx**: Temporary route outage; retry or try different points.
- **Geocoding**: Use clear `City, ST` format; respect rate limits.

---

## Roadmap

- Truck-specific routing profiles
- State line detection and state abbreviations per day
- Persistent trips and printable PDF logs
- ORS/paid routing provider with quota and SLAs

---

## License

See `LICENSE` file.
