const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function getJson(path, params = null) {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v)
    })
  }
  const res = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json()
}

async function patchJson(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`)
  return res.json()
}

export const api = {
  health: () => getJson('/api/health'),
  coastalState: (lat = 15.2993, lon = 73.97, refresh = false) =>
    getJson('/api/coastal-state', { lat, lon, refresh: refresh ? 'true' : undefined }),
  sensors: (zoneId = null, lat = null, lon = null) =>
    getJson('/api/sensors', { zone_id: zoneId, lat, lon }),
  latestReadings: () => getJson('/api/sensors/latest/readings'),
  events: () => getJson('/api/events'),
  event: (eventId) => getJson(`/api/events/${eventId}`),
  anomalies: () => getJson('/api/anomalies'),
  assets: (zoneId = null) => getJson('/api/assets', { zone_id: zoneId }),
  forecast: (eventId) => getJson('/api/forecast', { event_id: eventId }),
  exposure: (eventId) => getJson('/api/exposure', { event_id: eventId }),
  marine: (lat = 15.2993, lon = 73.97, refresh = false) =>
    getJson('/api/marine', { lat, lon, refresh: refresh ? 'true' : undefined }),
  whatIf: (body) => postJson('/api/simulation/what-if', body),
  copilot: (message, eventId) =>
    postJson('/api/copilot', { message, event_id: eventId ?? null }),
  mlTelemetry: () => getJson('/api/ml/telemetry'),
  sosList: () => getJson('/api/sos'),
  submitSos: (body) => postJson('/api/sos', body),
  updateSos: (ticketId, status) => patchJson(`/api/sos/${ticketId}?status=${status}`),
  mitigation: (eventId, districtId = null) =>
    getJson('/api/mitigation', { event_id: eventId, district_id: districtId }),
  topologicalAnalysis: (districtId = 'goa', waterLevel = 2.0) =>
    getJson('/api/topological/analysis', { district_id: districtId, water_level: waterLevel }),
  authorizeDefense: (defenseId, districtId = null, waterLevel = 2.0) =>
    postJson(`/api/topological/defense/${defenseId}/authorize?district_id=${districtId || ''}&water_level=${waterLevel}`, {}),
  geo: (zoneId = null, lat = null, lon = null) =>
    getJson('/api/geo', { zone_id: zoneId, lat, lon }),
  scenario: (zoneId = null) => getJson('/api/scenario', { zone_id: zoneId }),
  scenarioSnapshot: (t, zoneId = null, lat = null, lon = null, live = true) =>
    getJson('/api/scenario/snapshot', { t, zone_id: zoneId, lat, lon, live: live ? 'true' : 'false' }),
  activateLocation: (zoneId, lat = null, lon = null) =>
    postJson(`/api/locations/${zoneId}/activate${lat && lon ? `?lat=${lat}&lon=${lon}` : ''}`, {}),
}

export function scenarioWsUrl() {
  const base = API_BASE.replace(/^http/, 'ws')
  return `${base}/ws/scenario`
}

export async function withFallback(promise, fallback) {
  try {
    return await promise
  } catch (err) {
    console.warn('[TIDALIS] API unavailable, using fallback:', err.message)
    return typeof fallback === 'function' ? fallback() : fallback
  }
}

export const FALLBACK = {
  health: { status: 'offline', service: 'TIDALIS', sensors: 0, events: 0 },
  empty: [],
  coastalState: {
    timestamp: new Date().toISOString(),
    latitude: 15.2993,
    longitude: 73.97,
    status: 'UNKNOWN',
    sensor_count: 0,
    active_events: 0,
  },
}

export { API_BASE }