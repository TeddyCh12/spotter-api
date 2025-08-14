from datetime import datetime, timezone, timedelta
from django.http import HttpResponse
from dateutil import parser as dtparser
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import PlanTripInput
from .routing import geocode_place, osrm_route, point_on_polyline
from .hos import plan_schedule, parse_start_time
from .logbook import render_svg, normalize_segments
from rest_framework.exceptions import ValidationError

STATE_ABBR = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO",
    "Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID",
    "Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA",
    "Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS",
    "Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ",
    "New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
    "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD",
    "Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA",
    "West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY"
}

def _compact_place(display_name: str) -> str:
    # "City, County, State, United States" -> "City, ST"
    if not display_name:
        return ""
    # drop "United States" and "County" tokens
    parts = [p.strip() for p in display_name.replace(" United States", "").split(",") if p.strip()]
    if not parts:
        return display_name
    city = parts[0]
    # try last part as state
    st = parts[-1]
    st_abbr = STATE_ABBR.get(st, (st[:2].upper() if len(st) > 2 and st.isalpha() else st))
    return f"{city}, {st_abbr}"

def _to_dt(day_date_str, hhmm, tz):
    day = datetime.strptime(day_date_str, "%Y-%m-%d").date()
    if hhmm == "24:00":
        return datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz) + timedelta(days=1)
    hh, mm = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)

def _drive_hours_until(days, stop_dt, tz):
    """Sum driving hours from trip start until stop_dt."""
    total_h = 0.0
    for day in days:
        for seg in day["segments"]:
            a = _to_dt(day["date"], seg["from"], tz)
            b = _to_dt(day["date"], seg["to"], tz)
            # add only the overlap that occurs before stop_dt
            if b <= a:
                b += timedelta(days=1)
            if a >= stop_dt:
                return total_h
            end = min(b, stop_dt)
            if seg["status"] == "D" and end > a:
                total_h += (end - a).total_seconds() / 3600.0
    return total_h

def _labels_for_day(day_date_str, stops, tz):
    labels = []
    for s in stops:
        t = dtparser.parse(s["at_iso"]).astimezone(tz)
        if t.date().isoformat() != day_date_str:
            continue
        kind = s["type"]
        if kind == "pickup_on_duty":
            text = f"Pre-trip/TIV — {_compact_place(s.get('near','')) or 'Pickup'}"
        elif kind == "break_30min":
            text = "30-min break"
        elif kind == "overnight_off":
            text = "10-hr break"
        elif kind == "dropoff_on_duty":
            text = f"Post-trip/TIV — {_compact_place(s.get('near','')) or 'Dropoff'}"
        elif kind == "fuel_stop":
            text = "Fuel stop"
        else:
            text = kind.replace("_", " ").title()
        labels.append({"time": t.strftime("%H:%M"), "text": text})
    return sorted(labels, key=lambda L: L["time"])

def _dt_at_drive_fraction(days, tz, fraction: float):
    """Return datetime at which the cumulative driving reaches `fraction` of total driving."""
    # total driving hours in schedule
    total_drive = 0.0
    for d in days:
        for seg in d["segments"]:
            if seg["status"] != "D":
                continue
            a = _to_dt(d["date"], seg["from"], tz)
            b = _to_dt(d["date"], seg["to"], tz)
            if b <= a:
                b += timedelta(days=1)
            total_drive += (b - a).total_seconds() / 3600.0

    if total_drive <= 1e-9:
        # no driving — just return the start of the first day
        return _to_dt(days[0]["date"], "00:00", tz)

    target = max(0.0, min(1.0, float(fraction))) * total_drive
    cum = 0.0
    for d in days:
        for seg in d["segments"]:
            if seg["status"] != "D":
                continue
            a = _to_dt(d["date"], seg["from"], tz)
            b = _to_dt(d["date"], seg["to"], tz)
            if b <= a:
                b += timedelta(days=1)
            dur = (b - a).total_seconds() / 3600.0
            if cum + dur >= target:
                return a + timedelta(hours=(target - cum))
            cum += dur

    # Fallback: end of last day
    return _to_dt(days[-1]["date"], "24:00", tz)

@api_view(["POST"])
def plan_trip(request):
    ser = PlanTripInput(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data

    errors = {}

    # geocode
    try:
        cur = geocode_place(data["current_location"])
    except Exception:
        errors["current_location"] = ["We couldn't find that place. Try 'City, ST' (e.g., 'Dallas, TX')."]

    try:
        pu  = geocode_place(data["pickup_location"])
    except Exception:
        errors["pickup_location"] = ["We couldn't find the pickup location. Try 'City, ST' or a full address."]

    try:
        do  = geocode_place(data["dropoff_location"])
    except Exception:
        errors["dropoff_location"] = ["We couldn't find the dropoff location. Try 'City, ST' or a full address."]

    if errors:
        raise ValidationError(errors)

    # build route current->pickup->dropoff
    points = [(cur["lng"], cur["lat"]), (pu["lng"], pu["lat"]), (do["lng"], do["lat"])]
    
    try:
        route = osrm_route(points)
    except Exception:
        return Response(
            {"detail": "We couldn't compute a route between those locations. Please try again."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # HOS plan
    start_dt = parse_start_time(data.get("start_time_iso"))
    schedule = plan_schedule(
        total_drive_hours = route["duration_hours"],
        start_dt = start_dt,
        current_cycle_used = float(data["current_cycle_used_hours"])
    )

    # Enrich stops with coords along the route
    enriched_stops = []
    total_drive_h = route["duration_hours"]
    for s in schedule["stops"]:
        t = dict(s)
        if s["type"] == "pickup_on_duty":
            t["lat"], t["lng"], t["near"] = pu["lat"], pu["lng"], pu["display_name"]
        elif s["type"] == "dropoff_on_duty":
            t["lat"], t["lng"], t["near"] = do["lat"], do["lng"], do["display_name"]
        else:
            # break / overnight: place on route by drive progress fraction
            stop_dt = dtparser.parse(s["at_iso"])
            drive_h = _drive_hours_until(schedule["days"], stop_dt, start_dt.tzinfo)
            frac = 0.0 if total_drive_h <= 0 else min(max(drive_h / total_drive_h, 0.0), 1.0)
            p = point_on_polyline(route["polyline"], frac)
            t["lat"], t["lng"], t["near"] = p["lat"], p["lng"], None
        enriched_stops.append(t)

    # fuel stops every ~1000 miles as route markers
    dist_miles = route["distance_miles"]
    if dist_miles >= 1000:
        fuel_count = int(dist_miles // 1000)
        for i in range(1, fuel_count + 1):
            frac = (i * 1000.0) / dist_miles
            when = _dt_at_drive_fraction(schedule["days"], start_dt.tzinfo, frac)
            p = point_on_polyline(route["polyline"], frac)
            enriched_stops.append({
                "type": "fuel_stop",
                "at_iso": when.isoformat(),
                "duration_min": 0,
                "lat": p["lat"],
                "lng": p["lng"],
                "near": None,
            })



    normalized_days = []
    for day in schedule["days"]:
        normalized_days.append({
            "date": day["date"],
            "segments": normalize_segments(day["segments"]),
            "totals": day.get("totals", {}),
            "labels": _labels_for_day(day["date"], enriched_stops, start_dt.tzinfo),
        })

    out = {
        "polyline": route["polyline"],
        "summary": {
            "distance_miles": round(route["distance_miles"], 1),
            "drive_hours": round(route["duration_hours"], 2),
            "cycle_used_hours": round(schedule["summary"]["cycle_used_hours"], 2),
            "cycle_max_hours": schedule["summary"]["cycle_max_hours"],
            "cycle_exceeded": schedule["summary"]["cycle_exceeded"]
        },
        "places": {
            "current": cur,
            "pickup": pu,
            "dropoff": do
        },
        "stops": enriched_stops,
        "days": normalized_days
    }
    return Response(out, status=status.HTTP_200_OK)

@api_view(["POST"])
def render_logbook(request):
    date = request.data.get("date")
    segments = request.data.get("segments")
    labels = request.data.get("labels")
    if not date or not segments:
        return Response({"detail": "Provide JSON with 'date' and 'segments'."}, status=400)
    svg = render_svg(date, segments, labels=labels)
    return HttpResponse(svg, content_type="image/svg+xml")