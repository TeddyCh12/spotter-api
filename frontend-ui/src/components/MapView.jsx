import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { decodePolyline6 } from "../lib/polyline6";

export default function MapView({ polyline, places, stops }) {
  const mapRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    // Basic OSM tiles
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
      center: [-98.5, 39.8],
      zoom: 3.5,
    });
    mapRef.current = map;

    map.on("load", () => {
      if (!polyline) return;

      const lineCoords = decodePolyline6(polyline);
      const geo = {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: lineCoords },
          },
        ],
      };

      map.addSource("route", { type: "geojson", data: geo });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: { "line-width": 4 },
      });

      // Markers for current / pickup / dropoff
      const pins = [
        { id: "current", ...places?.current },
        { id: "pickup", ...places?.pickup },
        { id: "dropoff", ...places?.dropoff },
      ].filter(Boolean);

      pins.forEach(p => {
        new maplibregl.Marker().setLngLat([p.lng, p.lat]).setPopup(
          new maplibregl.Popup({ offset: 12 }).setText(p.display_name || p.id)
        ).addTo(map);
      });

      // Optional: small markers for breaks/overnights
      (stops || []).forEach(s => {
        if (typeof s.lng !== "number" || typeof s.lat !== "number") return;
        new maplibregl.Marker({ scale: 0.6 })
          .setLngLat([s.lng, s.lat])
          .setPopup(new maplibregl.Popup({ offset: 8 }).setText(s.type))
          .addTo(map);
      });

      // Fit bounds to route
      const lngs = lineCoords.map(c => c[0]);
      const lats = lineCoords.map(c => c[1]);
      const min = [Math.min(...lngs), Math.min(...lats)];
      const max = [Math.max(...lngs), Math.max(...lats)];
      map.fitBounds([min, max], { padding: 40, duration: 600 });
    });

    return () => mapRef.current?.remove();
  }, [polyline, places, stops]);

  return <div ref={containerRef} className="w-full h-96 rounded-xl border" />;
}
