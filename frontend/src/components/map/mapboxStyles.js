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
  'CRITICAL', '#f43f5e',
  'HIGH', '#f97316',
  'MODERATE', '#eab308',
  '#10b981',
]

export const FACILITY_COLOR_MATCH = [
  'match',
  ['get', 'kind'],
  'hospital', '#ec4899',
  'shelter', '#10b981',
  'fire_station', '#f97316',
  'police', '#3b82f6',
  'substation', '#eab308',
  'water_plant', '#06b6d4',
  'pumping_station', '#14b8a6',
  'port', '#a855f7',
  '#38bdf8',
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
