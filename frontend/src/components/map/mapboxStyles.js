export const MAPBOX_STYLES = {
  dark: {
    id: 'dark',
    name: 'Tactical Dark',
    url: 'mapbox://styles/mapbox/dark-v11',
  },
  satellite: {
    id: 'satellite',
    name: 'Satellite Streets',
    url: 'mapbox://styles/mapbox/satellite-streets-v12',
  },
  night: {
    id: 'night',
    name: 'Navigation Night',
    url: 'mapbox://styles/mapbox/navigation-night-v1',
  },
}

export const RISK_MATCH = [
  'match',
  ['get', 'risk_level'],
  'CRITICAL', '#fb7185',
  'HIGH', '#fb923c',
  'MODERATE', '#fbbf24',
  '#34d399',
]

// Approximate geodesic circle as a polygon (radius in km)
export function circlePolygon(lon, lat, radiusKm, points = 36) {
  const dLat = radiusKm / 111.32
  const dLon = radiusKm / (111.32 * Math.cos((lat * Math.PI) / 180))
  const coords = []
  for (let i = 0; i < points; i++) {
    const a = (i / points) * Math.PI * 2
    coords.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)])
  }
  coords.push(coords[0])
  return { type: 'Polygon', coordinates: [coords] }
}
