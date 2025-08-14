from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparser

OFF="OFF"; SB="SB"; D="D"; ON="ON"

MAX_DRIVE_DAY = 11.0     # hours
MAX_DUTY_WIN  = 14.0     # hours on-duty window
BREAK_AFTER_D = 8.0      # hours driving before 30-min break
BREAK_MIN     = 0.5      # hours (30 min)
OVERNIGHT_OFF = 10.0     # hours
CYCLE_MAX     = 70.0     # hours over 8 days

DEFAULT_START_HOUR = 8.0

QUANT_MIN = 5

def _h(h): 
    return timedelta(hours=h)

def _fmt(dt: datetime) -> str:
    """Round to nearest QUANT_MIN minutes and format HH:MM."""
    mins = dt.hour * 60 + dt.minute
    # round to nearest QUANT_MIN
    q = int(round(mins / QUANT_MIN) * QUANT_MIN)
    q = max(0, min(24*60, q))
    if q == 24*60:
        return "24:00"
    return f"{q//60:02d}:{q%60:02d}"

def plan_schedule(total_drive_hours: float, start_dt: datetime, current_cycle_used: float):
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    remaining_drive = total_drive_hours
    cursor = start_dt

    days = []
    stops = []
    cycle_used = current_cycle_used

    def _span_hours(a, b):
        def mins(hhmm: str) -> int:
            if hhmm == "24:00":
                return 24 * 60
            hh, mm = map(int, hhmm.split(":"))
            return hh * 60 + mm
        am = mins(a)
        bm = mins(b)
        if bm <= am:
            bm += 24 * 60
        return (bm - am) / 60.0

    def push_day(day_date, segments):
        # compute totals
        totals = {OFF:0.0, SB:0.0, D:0.0, ON:0.0}
        for s in segments:
            t = _span_hours(s["from"], s["to"])
            totals[s["status"]] += t
        days.append({"date": day_date.strftime("%Y-%m-%d"), "segments": segments, "totals": totals})

    first_day = True
    while remaining_drive > 1e-6:
        day_start = cursor
        day_date = day_start.date()
        duty_elapsed = 0.0
        drive_today = 0.0
        since_break_drive = 0.0
        segments = []

        # 1h ON at pickup only on first day at the beginning
        if first_day:
            on1_from = day_start
            on1_to = on1_from + _h(1.0)
            segments.append({"status": ON, "from": _fmt(on1_from), "to": _fmt(on1_to)})
            duty_elapsed += 1.0
            cycle_used += 1.0
            stops.append({"type":"pickup_on_duty", "at_iso": on1_from.isoformat(), "duration_min": 60})
            cursor = on1_to
            first_day = False

        while remaining_drive > 1e-6:
            if since_break_drive >= BREAK_AFTER_D - 1e-9:
                # Insert 30-min OFF
                br_from = cursor
                br_to = br_from + _h(BREAK_MIN)
                segments.append({"status": OFF, "from": _fmt(br_from), "to": _fmt(br_to)})
                duty_elapsed += BREAK_MIN
                cursor = br_to
                since_break_drive = 0.0
                stops.append({"type":"break_30min", "at_iso": br_from.isoformat(), "duration_min": 30})
                if duty_elapsed >= MAX_DUTY_WIN - 1e-9:
                    break

            # Max drive we can still do today
            drive_left_today = min(MAX_DRIVE_DAY - drive_today, MAX_DUTY_WIN - duty_elapsed)
            if drive_left_today <= 1e-9:
                break

            chunk = min(remaining_drive, drive_left_today, BREAK_AFTER_D - since_break_drive)
            if chunk <= 1e-9:
                chunk = min(remaining_drive, drive_left_today)

            drv_from = cursor
            drv_to = drv_from + _h(chunk)
            segments.append({"status": D, "from": _fmt(drv_from), "to": _fmt(drv_to)})

            remaining_drive -= chunk
            drive_today += chunk
            duty_elapsed += chunk
            since_break_drive += chunk
            cycle_used += chunk
            cursor = drv_to

            if drive_today >= MAX_DRIVE_DAY - 1e-9 or duty_elapsed >= MAX_DUTY_WIN - 1e-9:
                break

        if remaining_drive <= 1e-6:
            if duty_elapsed + 1.0 <= MAX_DUTY_WIN + 1e-9:
                on2_from = cursor
                on2_to = on2_from + _h(1.0)
                segments.append({"status": ON, "from": _fmt(on2_from), "to": _fmt(on2_to)})
                duty_elapsed += 1.0
                cycle_used += 1.0
                stops.append({"type":"dropoff_on_duty", "at_iso": on2_from.isoformat(), "duration_min": 60})
                cursor = on2_to
            else:
                # We'll place drop-off tomorrow after the overnight
                pass

        logical_off_start = cursor

        end_of_day = datetime.combine(
            day_date, datetime.max.time().replace(hour=23, minute=59), tzinfo=cursor.tzinfo
        ) + timedelta(minutes=1)
        if cursor < end_of_day:
            segments.append({"status": OFF, "from": _fmt(cursor), "to": "24:00"})
        push_day(day_date, segments)

        if remaining_drive > 1e-6 or (remaining_drive <= 1e-6 and duty_elapsed + 1.0 > MAX_DUTY_WIN - 1e-9):
            overnight_start = logical_off_start
            overnight_end = overnight_start + _h(OVERNIGHT_OFF)
            stops.append({
                "type": "overnight_off",
                "at_iso": overnight_start.isoformat(),
                "duration_min": int(OVERNIGHT_OFF * 60),
            })

            cursor = overnight_end

            if remaining_drive <= 1e-6:
                on2_from = cursor
                on2_to = on2_from + _h(1.0)
                day_date = on2_from.date()
                segments = [{"status": ON, "from": _fmt(on2_from), "to": _fmt(on2_to)}]
                stops.append({"type": "dropoff_on_duty", "at_iso": on2_from.isoformat(), "duration_min": 60})
                cursor = on2_to
                segments.append({"status": OFF, "from": _fmt(cursor), "to": "24:00"})
                push_day(day_date, segments)

    cycle_exceeded = (cycle_used > CYCLE_MAX + 1e-9)

    return {
        "days": days,
        "stops": stops,
        "summary": {
            "cycle_used_hours": cycle_used,
            "cycle_max_hours": CYCLE_MAX,
            "cycle_exceeded": cycle_exceeded
        }
    }

def parse_start_time(start_time_iso):
    if not start_time_iso:
        now = datetime.now(timezone.utc)
        hour = int(DEFAULT_START_HOUR)
        minute = int(round((DEFAULT_START_HOUR - hour) * 60))
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if isinstance(start_time_iso, datetime):
        dt = start_time_iso
    else:
        dt = dtparser.parse(start_time_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
