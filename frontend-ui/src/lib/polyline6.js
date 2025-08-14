// OSRM returns polyline6; this decodes to [ [lng, lat], ... ] for MapLibre
export function decodePolyline6(str) {
  let index = 0, lat = 0, lng = 0, coords = [];

  const shiftChunk = () => {
    let result = 0, shift = 0, b;
    do {
      b = str.charCodeAt(index++) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);
    return (result & 1) ? ~(result >> 1) : (result >> 1);
  };

  while (index < str.length) {
    lat += shiftChunk();
    lng += shiftChunk();
    coords.push([lng / 1e6, lat / 1e6]); // [lng,lat]
  }
  return coords;
}
