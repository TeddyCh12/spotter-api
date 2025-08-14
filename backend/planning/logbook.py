from typing import List, Dict

LANES = ["OFF", "SB", "D", "ON"]  # top→bottom

def _hhmm_to_min(hhmm: str) -> int:
    if hhmm == "24:00":
        return 24 * 60
    hh, mm = map(int, hhmm.split(":"))
    return max(0, min(24*60, hh * 60 + mm))

def _min_to_hhmm(m: int) -> str:
    m = max(0, min(24*60, m))
    if m == 24*60:
        return "24:00"
    return f"{m//60:02d}:{m%60:02d}"

def _wrap_text(s: str, max_len: int = 24, max_lines: int = 2):
    words = s.split()
    out, line = [], ""
    for w in words:
        if len(line) + (1 if line else 0) + len(w) <= max_len:
            line = f"{line} {w}".strip()
        else:
            out.append(line)
            line = w
        if len(out) >= max_lines:
            break
    if line and len(out) < max_lines:
        out.append(line)
    # ellipsis if we still truncated
    joined = " ".join(words)
    if " ".join(out) != joined and len(out) == max_lines:
        out[-1] = (out[-1][:-1] + "…") if len(out[-1]) >= 2 else "…"
    return out

def _escape(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def normalize_segments(segments: List[Dict]) -> List[Dict]:
    """
    Normalize a day's segments to fully cover 00:00..24:00.
    - Split segments that pass midnight into two pieces.
    - Trim overlaps.
    - Fill gaps with OFF.
    - Merge adjacent segments with the same status.
    """
    parsed = []
    for s in (segments or []):
        st = s["status"]
        start = _hhmm_to_min(s["from"])
        end   = _hhmm_to_min(s["to"])

        if end == start:
            # zero-length, ignore
            continue

        if end < start:
            # spans midnight -> split into [start..24:00] and [00:00..end]
            parsed.append((start, 24 * 60, st))
            parsed.append((0, end, st))
        else:
            parsed.append((start, end, st))

    parsed.sort(key=lambda x: x[0])

    out: List[Dict] = []
    last_end = 0

    for start, end, status in parsed:
        # trim overlap
        if start < last_end:
            start = last_end
        if start >= end:
            continue

        # fill any gap with OFF
        if start > last_end:
            out.append({
                "status": "OFF",
                "from": _min_to_hhmm(last_end),
                "to": _min_to_hhmm(start),
            })

        # merge if same lane touches
        if out and out[-1]["status"] == status and out[-1]["to"] == _min_to_hhmm(start):
            out[-1]["to"] = _min_to_hhmm(end)
        else:
            out.append({
                "status": status,
                "from": _min_to_hhmm(start),
                "to": _min_to_hhmm(end),
            })

        last_end = end

    # trailing OFF to midnight
    if last_end < 24 * 60:
        out.append({"status": "OFF", "from": _min_to_hhmm(last_end), "to": "24:00"})

    # no input segments -> whole day OFF
    if not parsed and not segments:
        out = [{"status": "OFF", "from": "00:00", "to": "24:00"}]

    return out

def render_svg(day_date: str, segments: List[Dict], labels: List[Dict]=None) -> str:
    """
    segments: [{status, from, to}] times as "HH:MM" 24h.
    Returns SVG string.
    """
    # ✅ normalize to full-day first
    segments = normalize_segments(segments)

    width, height = 1000, 320
    ml, mt, mr, mb = 60, 30, 20, 90
    inner_w = width - ml - mr
    lane_h = (height - mt - mb) / (len(LANES) - 1)

    def x_of(hhmm: str) -> float:
        hh, mm = map(int, hhmm.split(":"))
        minutes = hh * 60 + mm
        return ml + inner_w * (minutes / 1440.0)

    def y_of(status: str) -> float:
        idx = LANES.index(status)
        return mt + lane_h * idx

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="#ddd"/>')

    # vertical hour lines + labels
    for h in range(25):
        x = ml + inner_w * (h / 24.0)
        parts.append(f'<line x1="{x}" y1="{mt-10}" x2="{x}" y2="{height-mb}" stroke="#e5e5e5" stroke-width="1"/>')
        if h < 24:
            parts.append(f'<text x="{x+2}" y="{mt-15}" font-size="10" fill="#555">{h:02d}</text>')

    # horizontal lanes + labels
    for st in LANES:
        y = y_of(st)
        parts.append(f'<line x1="{ml}" y1="{y}" x2="{width-mr}" y2="{y}" stroke="#bbb" stroke-width="1.5"/>')
        parts.append(f'<text x="10" y="{y+4}" font-size="12" fill="#333">{st}</text>')

    # thick duty lines with vertical connectors
    last_x = None
    last_y = None
    for seg in segments:
        st = seg["status"]
        x1 = x_of(seg["from"])
        x2 = x_of(seg["to"]) if seg["to"] != "24:00" else ml + inner_w
        y  = y_of(st)
        if last_x is not None and abs(x1 - last_x) < 1e-6 and last_y is not None and abs(y - last_y) > 1e-6:
            parts.append(f'<line x1="{x1}" y1="{last_y}" x2="{x1}" y2="{y}" stroke="black" stroke-width="3"/>')
        parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="black" stroke-width="3"/>')
        last_x, last_y = x2, y

    if labels:
        grid_bottom = height - mb

        for lab in labels:
            x = x_of(lab["time"])

            # subtle dashed guide from grid to axis
            parts.append(
                f'<line x1="{x}" y1="{grid_bottom-50}" x2="{x}" y2="{grid_bottom}" '
                f'stroke="#9aa0a6" stroke-width="1" stroke-dasharray="2,2"/>'
            )

            # wrap to two short lines and draw centered at x
            lines = _wrap_text(lab.get("text", ""), max_len=24, max_lines=2)
            base_y = grid_bottom + 14
            for i, line in enumerate(lines):
                y = base_y + i * 12
                parts.append(
                    f'<text x="{x}" y="{y}" text-anchor="middle" font-size="11" fill="#374151">'
                    f'{_escape(line)}</text>'
                )

    parts.append(f'<text x="{ml}" y="{height-12}" font-size="12" fill="#333">Date: {day_date}</text>')
    parts.append('</svg>')
    return "".join(parts) 