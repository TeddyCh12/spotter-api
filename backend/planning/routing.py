import math, bisect
import time
from functools import lru_cache
import requests

OSRM_BASE = "https://router.project-osrm.org"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {"User-Agent": "SpotterAssessment/1.0 (contact: dev@example.com)"}

@lru_cache(maxsize=256)
def geocode_place(q: str):
    """Return dict: {lat, lng, display_name} using Nominatim."""
    params = {"format": "json", "q": q, "limit": 1}
    r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError(f"Geocode failed for: {q}")
    item = data[0]
    # be polite to Nominatim
    time.sleep(1.0)
    return {
        "lat": float(item["lat"]),
        "lng": float(item["lon"]),
        "display_name": item.get("display_name", q)
    }

def osrm_route(points):
    """
    points: list of (lng, lat). Return dict {polyline, distance_miles, duration_hours, distance_m, duration_s}
    """
    if len(points) < 2:
        raise ValueError("Need at least 2 points")
    coords = ";".join([f"{lng},{lat}" for (lng, lat) in points])
    url = f"{OSRM_BASE}/route/v1/driving/{coords}"
    params = {"overview": "full", "geometries": "polyline6", "annotations":"false", "steps":"false"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    js = r.json()
    if js.get("code") != "Ok" or not js.get("routes"):
        raise ValueError(f"OSRM route failed: {js}")
    route = js["routes"][0]
    dist_m = route["distance"]
    dur_s = route["duration"]
    poly = route["geometry"]
    return {
        "polyline": poly,
        "distance_m": dist_m,
        "duration_s": dur_s,
        "distance_miles": dist_m * 0.000621371,
        "duration_hours": dur_s / 3600.0
    }

def decode_polyline6(polyline: str):
    coords = []
    index = 0
    lat = 0
    lng = 0
    while index < len(polyline):
        # latitude
        result, shift, b = 1, 0, 0x20
        while b >= 0x20:
            b = ord(polyline[index]) - 63; index += 1
            result += (b & 0x1f) << shift; shift += 5
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        # longitude
        result, shift, b = 1, 0, 0x20
        while b >= 0x20:
            b = ord(polyline[index]) - 63; index += 1
            result += (b & 0x1f) << shift; shift += 5
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        coords.append((lat / 1e6, lng / 1e6))
    return coords

def _hav_m(a, b):
    R = 6371000.0
    (lat1, lon1), (lat2, lon2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    t = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(t))

def _cumdist(points):
    cum = [0.0]
    total = 0.0
    for i in range(1, len(points)):
        total += _hav_m(points[i-1], points[i])
        cum.append(total)
    return cum, total

def point_on_polyline(polyline: str, fraction: float):
    """Return {'lat','lng'} at given fraction (0..1) along the polyline."""
    pts = decode_polyline6(polyline)
    if len(pts) < 2:
        lat, lng = pts[0]
        return {"lat": lat, "lng": lng}
    fraction = max(0.0, min(1.0, float(fraction)))
    cum, total = _cumdist(pts)
    s = total * fraction
    i = bisect.bisect_left(cum, s)
    if i == 0: 
        lat, lng = pts[0]; return {"lat": lat, "lng": lng}
    if i >= len(pts): 
        lat, lng = pts[-1]; return {"lat": lat, "lng": lng}
    s0, s1 = cum[i-1], cum[i]
    t = 0.0 if s1 == s0 else (s - s0) / (s1 - s0)
    (lat0, lon0), (lat1, lon1) = pts[i-1], pts[i]
    return {"lat": lat0 + t*(lat1-lat0), "lng": lon0 + t*(lon1-lon0)}
