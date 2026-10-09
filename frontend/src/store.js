import { create } from 'zustand'
import { api, withFallback, FALLBACK, scenarioWsUrl } from './lib/api'

const highestConfidence = (events) =>
  [...(events ?? [])].sort((a, b) => b.confidence - a.confidence)[0] ?? null

const STEP_H = 0.25

// module-scoped live stream handles (not part of reactive state)
let scenarioSocket = null
let scenarioSocketPromise = null
let localTimer = null

export const useTidalis = create((set, get) => ({
  // --- data ---------------------------------------------------------------
  health: FALLBACK.health,
  coastalState: FALLBACK.coastalState,
  marineData: null,
  lastLiveUpdate: null,
  isLiveRefreshing: false,
  userLocation: null,
  activeLocation: { lat: 15.2993, lon: 73.97, name: 'Coastal Command Station' },
  sensors: [],
  readings: [],
  events: [],
  assets: [],
  loading: true,
  online: true,

  // --- selection ----------------------------------------------------------
  selectedEventId: null,
  forecast: null,
  exposures: [],
  simulation: null,
  simulating: false,

  // --- layers -------------------------------------------------------------
  layers: {
    sensors: true,
    events: true,
    exposure: true,
    simulation: true,
    sos: true,
    zones: true,
    flood: true,
    roads: true,
    buildings: true,
    facilities: true,
  },

  // --- new features -------------------------------------------------------
  telemetry: null,
  sosTickets: [],
  mitigationPlan: null,

  // --- scenario timeline --------------------------------------------------
  scenarioMeta: null,
  geo: null,
  snapshot: null,
  scenarioT: 0,
  scenarioPlaying: false,
  scenarioLive: false,
  scenarioReady: false,
  selectedZoneId: 'B',

  // --- mapbox & layout state ---------------------------------------------
  mapboxToken:
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_MAPBOX_TOKEN) ||
    (typeof localStorage !== 'undefined' ? localStorage.getItem('tidalis_mapbox_token') || '' : ''),
  mapStyle: 'dark', // 'dark' | 'satellite' | 'night'
  leftRailCollapsed: false,
  inspectorCollapsed: false,
  inspectorTab: 'brief', // 'brief' | 'priorities' | 'zone' | 'event'
  operationsOpen: false,
  operationsTab: 'Copilot',

  setMapboxToken(token) {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('tidalis_mapbox_token', token)
    }
    set({ mapboxToken: token })
  },
  setMapStyle(mapStyle) {
    set({ mapStyle })
  },
  toggleLeftRail() {
    set((s) => ({ leftRailCollapsed: !s.leftRailCollapsed }))
  },
  setLeftRailCollapsed(collapsed) {
    set({ leftRailCollapsed: collapsed })
  },
  toggleInspector() {
    set((s) => ({ inspectorCollapsed: !s.inspectorCollapsed }))
  },
  setInspectorCollapsed(collapsed) {
    set({ inspectorCollapsed: collapsed })
  },
  setInspectorTab(tab) {
    set({ inspectorTab: tab, inspectorCollapsed: false })
  },
  toggleOperations() {
    set((s) => ({ operationsOpen: !s.operationsOpen }))
  },
  setOperationsOpen(open) {
    set({ operationsOpen: open })
  },
  setOperationsTab(tab) {
    set({ operationsTab: tab, operationsOpen: true })
  },
  mapTarget: null,
  flyToTarget(target) {
    set({ mapTarget: { ...target, timestamp: Date.now() } })
  },

  // initialise: load everything once
  async init() {
    const [health, coastalState, marineData, sensors, readings, events, assets, telemetry, sosTickets] =
      await Promise.all([
        withFallback(api.health(), FALLBACK.health),
        withFallback(api.coastalState(15.2993, 73.97, true), FALLBACK.coastalState),
        withFallback(api.marine(15.2993, 73.97, true), null),
        withFallback(api.sensors(), FALLBACK.empty),
        withFallback(api.latestReadings(), FALLBACK.empty),
        withFallback(api.events(), FALLBACK.empty),
        withFallback(api.assets(), FALLBACK.empty),
        withFallback(api.mlTelemetry(), null),
        withFallback(api.sosList(), FALLBACK.empty),
      ])

    const top = highestConfidence(events)
    set({
      health,
      coastalState,
      marineData: marineData || coastalState.marine_data,
      lastLiveUpdate: new Date().toLocaleTimeString(),
      sensors,
      readings,
      events,
      assets,
      telemetry,
      sosTickets,
      loading: false,
      online: health.status === 'ok',
      selectedEventId: top?.event_id ?? null,
    })

    if (top) await get().loadEventDetails(top.event_id)
    get().initScenario()

    // Automatically check for browser geolocation on launch
    get().detectUserLocation()
  },

  detectUserLocation() {
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = Number(pos.coords.latitude.toFixed(4))
          const lon = Number(pos.coords.longitude.toFixed(4))
          get().setLocation(lat, lon, 'Live GPS Position')
        },
        (err) => {
          console.info('[TIDALIS] Geolocation fallback used:', err?.message)
        },
        { timeout: 8000, enableHighAccuracy: true }
      )
    }
  },

  setLocation(lat, lon, name = 'Current Position') {
    set({
      userLocation: { lat, lon, label: name },
      activeLocation: { lat, lon, name },
    })
    get().refreshLiveData(lat, lon)
  },

  async switchDistrict(districtId) {
    const districts = {
      goa: { lat: 15.2993, lon: 73.9700, name: 'Goa Coastal District', id: 'goa' },
      mangaluru: { lat: 12.9187, lon: 74.8598, name: 'Mangaluru Coastal District', id: 'mangaluru' },
      mumbai: { lat: 18.9667, lon: 72.8333, name: 'Mumbai Harbor District', id: 'mumbai' },
    }
    const d = districts[districtId] || districts.goa
    set({
      activeLocation: { lat: d.lat, lon: d.lon, name: d.name, districtId: d.id },
      userLocation: null,
    })
    await get().refreshLiveData(d.lat, d.lon, d.id)
  },

  async refreshLiveData(customLat, customLon, customZoneId) {
    const coords = get().userLocation || get().activeLocation || { lat: 15.2993, lon: 73.97 }
    const lat = typeof customLat === 'number' ? customLat : coords.lat
    const lon = typeof customLon === 'number' ? customLon : coords.lon
    const zoneId = customZoneId || get().activeLocation?.districtId || null
    set({ isLiveRefreshing: true })
    try {
      const [health, coastalState, marineData, readings, geo, snapshot, sensors, events] = await Promise.all([
        withFallback(api.health(), get().health),
        withFallback(api.coastalState(lat, lon, true), get().coastalState),
        withFallback(api.marine(lat, lon, true), get().marineData),
        withFallback(api.latestReadings(), get().readings),
        withFallback(api.geo(zoneId, lat, lon), get().geo),
        withFallback(api.scenarioSnapshot(get().scenarioT, zoneId, lat, lon, true), get().snapshot),
        withFallback(api.sensors(zoneId, lat, lon), get().sensors),
        withFallback(api.events(), get().events),
      ])
      const currentEvents = (events && events.length > 0) ? events : get().events
      const currentSelected = get().selectedEventId
      const validSelectedId = currentSelected && currentEvents.some(e => e.event_id === currentSelected)
        ? currentSelected
        : (currentEvents[0]?.event_id || null)

      set({
        health,
        coastalState,
        marineData: marineData || coastalState.marine_data,
        readings: (readings && readings.length > 0) ? readings : get().readings,
        geo: geo || get().geo,
        snapshot: snapshot || get().snapshot,
        sensors: (sensors && sensors.length > 0) ? sensors : get().sensors,
        events: currentEvents,
        selectedEventId: validSelectedId,
        lastLiveUpdate: new Date().toLocaleTimeString(),
        online: health.status === 'ok',
        isLiveRefreshing: false,
      })
      if (validSelectedId && (!get().mitigationPlan || validSelectedId !== currentSelected)) {
        get().loadMitigationPlan()
      }
    } catch (err) {
      console.warn('[TIDALIS] Live data refresh failed:', err)
      set({ isLiveRefreshing: false })
    }
  },

  // --- scenario timeline --------------------------------------------------
  async initScenario() {
    const coords = get().userLocation || get().activeLocation
    const lat = coords?.lat
    const lon = coords?.lon
    const [scenarioMeta, geo, snapshot] = await Promise.all([
      withFallback(api.scenario(), null),
      withFallback(api.geo(null, lat, lon), null),
      withFallback(api.scenarioSnapshot(0, null, lat, lon, true), null),
    ])
    set({
      scenarioMeta,
      geo,
      snapshot,
      scenarioT: 0,
      scenarioReady: Boolean(snapshot),
    })
    if (snapshot && !get().selectedZoneId) {
      set({ selectedZoneId: snapshot.priorities?.top_zone ?? 'B' })
    }
  },

  async seekScenario(t) {
    const value = Math.max(0, Math.min(5, Number(t)))
    set({ scenarioT: value })
    const coords = get().userLocation || get().activeLocation
    const snapshot = await withFallback(
      api.scenarioSnapshot(value, null, coords?.lat, coords?.lon, true),
      null
    )
    if (snapshot) set({ snapshot, scenarioT: snapshot.t_hours })
    return snapshot
  },

  _applyStreamMessage(message) {
    if (!message || typeof message !== 'object') return
    if (message.type === 'meta') {
      set({ scenarioMeta: message.scenario })
    } else if (message.type === 'snapshot') {
      set({
        snapshot: message.snapshot,
        scenarioT: message.snapshot.t_hours,
        scenarioReady: true,
      })
    } else if (message.type === 'status') {
      set({ scenarioPlaying: Boolean(message.playing), scenarioT: message.t })
      if (!message.playing && localTimer) {
        clearInterval(localTimer)
        localTimer = null
      }
    }
  },

  _ensureScenarioSocket() {
    if (scenarioSocket && scenarioSocket.readyState === WebSocket.OPEN) {
      return Promise.resolve(scenarioSocket)
    }
    if (scenarioSocketPromise) return scenarioSocketPromise

    scenarioSocketPromise = new Promise((resolve) => {
      let socket
      try {
        socket = new WebSocket(scenarioWsUrl())
      } catch (err) {
        console.warn('[TIDALIS] WebSocket unavailable:', err?.message)
        scenarioSocketPromise = null
        resolve(null)
        return
      }

      const timeout = setTimeout(() => {
        scenarioSocketPromise = null
        resolve(null)
      }, 4000)

      socket.onopen = () => {
        clearTimeout(timeout)
        scenarioSocket = socket
        set({ scenarioLive: true })
        scenarioSocketPromise = null
        resolve(socket)
      }
      socket.onmessage = (event) => {
        try {
          get()._applyStreamMessage(JSON.parse(event.data))
        } catch {
          /* ignore malformed frames */
        }
      }
      socket.onerror = () => {
        clearTimeout(timeout)
        set({ scenarioLive: false })
      }
      socket.onclose = () => {
        clearTimeout(timeout)
        set({ scenarioLive: false, scenarioPlaying: false })
        if (scenarioSocket === socket) scenarioSocket = null
        scenarioSocketPromise = null
      }
    })
    return scenarioSocketPromise
  },

  _sendStream(action, extra = {}) {
    if (scenarioSocket && scenarioSocket.readyState === WebSocket.OPEN) {
      scenarioSocket.send(JSON.stringify({ action, ...extra }))
      return true
    }
    return false
  },

  async playScenario() {
    const socket = await get()._ensureScenarioSocket()
    if (socket) {
      get()._sendStream('play')
      set({ scenarioPlaying: true, scenarioLive: true })
      return
    }
    // Fallback: step the timeline locally when no socket is available
    if (localTimer) return
    set({ scenarioPlaying: true })
    localTimer = setInterval(async () => {
      const t = get().scenarioT
      if (t >= 5) {
        clearInterval(localTimer)
        localTimer = null
        set({ scenarioPlaying: false })
        return
      }
      await get().seekScenario(t + STEP_H)
    }, 850)
  },

  pauseScenario() {
    const sent = get()._sendStream('pause')
    set({ scenarioPlaying: false })
    if (!sent && localTimer) {
      clearInterval(localTimer)
      localTimer = null
    }
  },

  resetScenario() {
    const sent = get()._sendStream('reset')
    set({ scenarioPlaying: false, scenarioT: 0 })
    if (!sent) {
      if (localTimer) {
        clearInterval(localTimer)
        localTimer = null
      }
      get().seekScenario(0)
    }
  },

  toggleScenarioPlay() {
    if (get().scenarioPlaying) get().pauseScenario()
    else get().playScenario()
  },

  selectZone(zoneId) {
    set({ selectedZoneId: zoneId, inspectorTab: 'zone', inspectorCollapsed: false })
  },

  async refreshHealth() {
    const health = await withFallback(api.health(), FALLBACK.health)
    set({ health, online: health.status === 'ok' })
  },

  async loadEventDetails(eventId) {
    if (!eventId) return
    set({ selectedEventId: eventId, simulation: null })
    const [forecast, exposures] = await Promise.all([
      withFallback(api.forecast(eventId), null),
      withFallback(api.exposure(eventId), FALLBACK.empty),
    ])
    set({ forecast, exposures })
    get().loadMitigationPlan()
  },

  selectEvent(eventId) {
    set({ inspectorTab: 'event', inspectorCollapsed: false })
    get().loadEventDetails(eventId)
  },

  async loadExposures() {
    const { selectedEventId } = get()
    if (!selectedEventId) return
    const exposures = await withFallback(
      api.exposure(selectedEventId),
      FALLBACK.empty,
    )
    set({ exposures })
  },

  async runWhatIf(scenario) {
    const { selectedEventId, events } = get()
    const activeEventId = (selectedEventId && events.some(e => e.event_id === selectedEventId))
      ? selectedEventId
      : (events[0]?.event_id || 'EVT-001')
    set({ simulating: true, selectedEventId: activeEventId })
    try {
      const simulation = await api.whatIf({ event_id: activeEventId, ...scenario })
      set({ simulation, simulating: false })
      return simulation
    } catch (err) {
      console.warn('[TIDALIS] What-If simulation API fallback active:', err.message)
      const ev = events.find(e => e.event_id === activeEventId) || events[0]
      const baseLat = ev?.latitude || 15.2993
      const baseLon = ev?.longitude || 73.97
      const fallbackSim = {
        event_id: activeEventId,
        scenario: scenario || {},
        steps: [
          { hours_ahead: 1, latitude: baseLat - 0.03, longitude: baseLon - 0.01, radius_km: 10.0, exposure_change_pct: 0 },
          { hours_ahead: 3, latitude: baseLat - 0.06, longitude: baseLon - 0.03, radius_km: 10.4, exposure_change_pct: 0 },
          { hours_ahead: 6, latitude: baseLat - 0.10, longitude: baseLon - 0.06, radius_km: 11.0, exposure_change_pct: 0 },
          { hours_ahead: 12, latitude: baseLat - 0.18, longitude: baseLon - 0.12, radius_km: 12.2, exposure_change_pct: 0 },
          { hours_ahead: 24, latitude: baseLat - 0.33, longitude: baseLon - 0.25, radius_km: 14.5, exposure_change_pct: 0 },
        ],
        total_exposure_change_pct: 0,
        generated_at: new Date().toISOString(),
      }
      set({ simulation: fallbackSim, simulating: false })
      return fallbackSim
    }
  },

  toggleLayer(name) {
    set((s) => ({ layers: { ...s.layers, [name]: !s.layers[name] } }))
  },

  async loadTelemetry() {
    const telemetry = await withFallback(api.mlTelemetry(), null)
    set({ telemetry })
  },

  async loadSosTickets() {
    const sosTickets = await withFallback(api.sosList(), FALLBACK.empty)
    set({ sosTickets })
  },

  async submitSosTicket(payload) {
    const newTicket = await api.submitSos(payload)
    const sosTickets = await withFallback(api.sosList(), FALLBACK.empty)
    set({ sosTickets })
    return newTicket
  },

  async updateSosTicketStatus(ticketId, status) {
    await api.updateSos(ticketId, status)
    get().loadSosTickets()
  },

  async loadMitigationPlan() {
    const { selectedEventId, activeLocation, events } = get()
    const activeEventId = (selectedEventId && events.some(e => e.event_id === selectedEventId))
      ? selectedEventId
      : (events[0]?.event_id || null)
    if (!activeEventId) {
      set({ mitigationPlan: null })
      return
    }
    const districtId = activeLocation?.districtId || null
    const mitigationPlan = await withFallback(
      api.mitigation(activeEventId, districtId),
      null,
    )
    set({ mitigationPlan, selectedEventId: activeEventId })
  },

  async authorizeBottleneckDefense(defenseId) {
    const { activeLocation, snapshot } = get()
    const districtId = activeLocation?.districtId || 'goa'
    const waterLevel = snapshot?.conditions?.water_level_m ?? 2.0
    try {
      const res = await api.authorizeDefense(defenseId, districtId, waterLevel)
      await Promise.all([
        get().refreshLiveData(null, null, districtId),
        get().loadMitigationPlan(),
      ])
      return res
    } catch (err) {
      console.warn('[TIDALIS] Failed authorizing defense:', err)
    }
  },
}))

