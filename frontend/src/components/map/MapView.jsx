import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { useTidalis } from '../../store'
import MapHUD from './MapHUD'
import MapLegend from './MapLegend'
import { MAPBOX_STYLES, RISK_MATCH, FACILITY_COLOR_MATCH, circlePolygon } from './mapboxStyles'
import { createPulseDot, createFacilityBadge, createBuoyBadge } from './pulseMarker'

const DEFAULT_ZOOM = 12.2

export default function MapView() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [pitched, setPitched] = useState(true)
  const [inputToken, setInputToken] = useState('')
  const [tokenError, setTokenError] = useState('')

  // Store state
  const mapboxToken = useTidalis((s) => s.mapboxToken)
  const setMapboxToken = useTidalis((s) => s.setMapboxToken)
  const mapStyle = useTidalis((s) => s.mapStyle)
  const userLocation = useTidalis((s) => s.userLocation)
  const activeLocation = useTidalis((s) => s.activeLocation)
  const events = useTidalis((s) => s.events)
  const sensors = useTidalis((s) => s.sensors)
  const readings = useTidalis((s) => s.readings)
  const assets = useTidalis((s) => s.assets)
  const selectedEventId = useTidalis((s) => s.selectedEventId)
  const layers = useTidalis((s) => s.layers)
  const simulation = useTidalis((s) => s.simulation)
  const selectEvent = useTidalis((s) => s.selectEvent)
  const loadExposures = useTidalis((s) => s.loadExposures)
  const geo = useTidalis((s) => s.geo)
  const snapshot = useTidalis((s) => s.snapshot)
  const selectZone = useTidalis((s) => s.selectZone)
  const selectedZoneId = useTidalis((s) => s.selectedZoneId)
  const sosTickets = useTidalis((s) => s.sosTickets)
  const mapTarget = useTidalis((s) => s.mapTarget)

  const centerCoords = useMemo(() => {
    if (geo?.meta?.center && Array.isArray(geo.meta.center) && geo.meta.center.length === 2) {
      return geo.meta.center
    }
    if (activeLocation?.lon && activeLocation?.lat) return [activeLocation.lon, activeLocation.lat]
    if (userLocation?.lon && userLocation?.lat) return [userLocation.lon, userLocation.lat]
    const evt = events.find((e) => e.event_id === selectedEventId) || events[0]
    if (evt?.longitude && evt?.latitude) return [evt.longitude, evt.latitude]
    return [73.97, 15.30]
  }, [geo, activeLocation, userLocation, events, selectedEventId])

  const hasValidToken = Boolean(mapboxToken && mapboxToken.startsWith('pk.'))
  const currentStyleUrl = useMemo(() => {
    return MAPBOX_STYLES[mapStyle]?.url || MAPBOX_STYLES.dark.url
  }, [mapStyle])

  const handleActivate = (e) => {
    e.preventDefault()
    const trimmed = inputToken.trim()
    if (!trimmed.startsWith('pk.')) {
      setTokenError('Token must start with "pk." (e.g. pk.eyJ1...)')
      return
    }
    setTokenError('')
    setMapboxToken(trimmed)
  }

  // ---------- derive geojson ------------------------------------------------
  const readingsBySensor = useMemo(() => {
    const map = {}
    for (const r of readings) map[r.sensor_id] = r
    return map
  }, [readings])

  const sensorGeo = useMemo(() => {
    const features = sensors.map((s) => {
      const r = readingsBySensor[s.sensor_id] ?? {}
      const lat = s.latitude ?? s.lat
      const lon = s.longitude ?? s.lon
      if (lat == null || lon == null) return null
      const anomalous = (r.turbidity ?? s.turbidity ?? 0) > 20 || (r.temperature ?? s.temperature ?? 0) > 31.0
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: {
          id: s.sensor_id,
          name: s.name || s.sensor_id,
          sensor_type: s.sensor_type ?? 'marine_buoy',
          anomalous: Boolean(anomalous),
          temperature: r.temperature ?? s.temperature,
          turbidity: r.turbidity ?? s.turbidity,
          ph: r.ph ?? s.ph,
          dissolved_oxygen: r.dissolved_oxygen ?? s.dissolved_oxygen,
          water_level_m: r.water_level_m ?? s.water_level_m ?? 0.85,
          wave_height_m: r.wave_height_m ?? s.wave_height_m ?? 1.2,
          precipitation_mm_hr: r.precipitation_mm_hr ?? s.precipitation_mm_hr ?? 0.0,
        },
      }
    }).filter(Boolean)
    return { type: 'FeatureCollection', features }
  }, [sensors, readingsBySensor])

  const eventGeo = useMemo(
    () => ({
      type: 'FeatureCollection',
      features: events.map((e) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [e.longitude, e.latitude] },
        properties: {
          id: e.event_id,
          severity: e.severity,
          confidence: e.confidence,
          description: e.description,
        },
      })),
    }),
    [events],
  )

  const exposureGeo = useMemo(() => {
    const event = events.find((e) => e.event_id === selectedEventId) || events[0]
    if (!event) return { type: 'FeatureCollection', features: [] }
    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: circlePolygon(event.longitude, event.latitude, event.radius_km || 12.0),
          properties: { id: event.event_id },
        },
      ],
    }
  }, [events, selectedEventId])

  const simulationGeo = useMemo(() => {
    if (!simulation || !Array.isArray(simulation.steps) || simulation.steps.length === 0) {
      return { type: 'FeatureCollection', features: [] }
    }
    const coords = simulation.steps.map((p) => [p.longitude, p.latitude])
    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: coords },
          properties: { label: 'projected' },
        },
        ...simulation.steps.map((p) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
          properties: { hours: p.hours_ahead, change: p.exposure_change_pct, radius: p.radius_km },
        })),
      ],
    }
  }, [simulation])

  const assetGeo = useMemo(
    () => ({
      type: 'FeatureCollection',
      features: assets.map((a) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [a.longitude, a.latitude] },
        properties: {
          id: a.asset_id,
          name: a.name,
          type: a.asset_type,
          sensitivity: a.sensitivity,
        },
      })),
    }),
    [assets],
  )

  const sosGeo = useMemo(
    () => ({
      type: 'FeatureCollection',
      features: (sosTickets || []).map((t) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [t.longitude, t.latitude] },
        properties: {
          id: t.ticket_id,
          name: t.name,
          urgency: t.urgency,
          status: t.status,
          method: t.rescue_method,
        },
      })),
    }),
    [sosTickets],
  )

  const boundaryGeo = useMemo(() => {
    if (!geo?.layers?.boundary) return { type: 'FeatureCollection', features: [] }
    return geo.layers.boundary
  }, [geo])

  const zoneGeo = useMemo(() => {
    if (!geo?.layers?.zones) return { type: 'FeatureCollection', features: [] }
    const states = new Map((snapshot?.zones ?? []).map((z) => [z.zone_id, z]))
    const isolated = new Set(snapshot?.isolation?.isolated_zones ?? [])
    return {
      type: 'FeatureCollection',
      features: geo.layers.zones.features.map((f) => {
        const state = states.get(f.properties.id)
        return {
          ...f,
          properties: {
            ...f.properties,
            risk_level: state?.risk_level ?? 'LOW',
            flood_probability: state?.flood_probability ?? 0,
            flood_depth_m: state?.flood_depth_m ?? 0,
            color: state?.risk_color ?? '#10b981',
            isolated: isolated.has(f.properties.id),
            selected: f.properties.id === selectedZoneId,
          },
        }
      }),
    }
  }, [geo, snapshot, selectedZoneId])

  const inundationGeo = useMemo(() => {
    if (!geo?.layers?.inundation) return { type: 'FeatureCollection', features: [] }
    const refWater = snapshot?.conditions?.water_level_m ?? 0.85
    return {
      type: 'FeatureCollection',
      features: geo.layers.inundation.features.map((f) => {
        const baseElev = f.properties.base_elevation_m || 1.0
        const depth = Math.max(0.05, Math.round((refWater - baseElev) * 100) / 100)
        let hazard = 'SHALLOW'
        if (depth > 1.0) hazard = 'CRITICAL'
        else if (depth > 0.4) hazard = 'HIGH'
        else if (depth > 0.15) hazard = 'MODERATE'
        return {
          ...f,
          properties: {
            ...f.properties,
            depth_m: depth,
            hazard_level: hazard,
          },
        }
      }),
    }
  }, [geo, snapshot])

  const roadGeo = useMemo(() => {
    if (!geo?.layers?.roads) return { type: 'FeatureCollection', features: [] }
    const blocked = new Map(
      (snapshot?.isolation?.blocked_roads ?? []).map((r) => [r.id, r]),
    )
    const bottlenecks = new Map(
      (snapshot?.isolation?.bottlenecks ?? []).map((b) => [b.road_id, b]),
    )
    return {
      type: 'FeatureCollection',
      features: geo.layers.roads.features.map((f) => {
        const status = blocked.get(f.properties.id)
        const b = bottlenecks.get(f.properties.id)
        return {
          ...f,
          properties: {
            ...f.properties,
            passable: !status,
            submersion_m: status?.submersion_m ?? 0,
            is_cut_edge: b?.is_cut_edge ?? false,
            betweenness_centrality: b?.betweenness_centrality ?? 0,
            defended: b?.defended ?? false,
            bottleneck_status: b?.status ?? (status ? 'SEVERED' : 'CLEAR'),
          },
        }
      }),
    }
  }, [geo, snapshot])

  const evacCorridorGeo = useMemo(() => {
    const corridors = snapshot?.isolation?.evacuation_corridors ?? []
    return {
      type: 'FeatureCollection',
      features: corridors.map((c) => ({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: c.coordinates,
        },
        properties: {
          id: c.id,
          name: c.name,
          origin_name: c.origin_name,
          destination_hub: c.destination_hub,
          distance_km: c.distance_km,
          estimated_minutes: c.estimated_minutes,
          status: c.status,
        },
      })),
    }
  }, [snapshot])

  const bottleneckGeo = useMemo(() => {
    const bottlenecks = snapshot?.isolation?.bottlenecks ?? []
    return {
      type: 'FeatureCollection',
      features: bottlenecks.map((b) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: b.coordinates,
        },
        properties: {
          id: b.id,
          road_id: b.road_id,
          name: b.name,
          ref: b.ref,
          classification: b.classification,
          deck_elevation_m: b.deck_elevation_m,
          water_on_deck_m: b.water_on_deck_m,
          is_cut_edge: b.is_cut_edge,
          betweenness_centrality: b.betweenness_centrality,
          status: b.status,
          isolated_population: b.isolated_population,
          defended: b.defended,
        },
      })),
    }
  }, [snapshot])

  const buildingGeo = useMemo(() => {
    if (!geo?.layers?.buildings) return { type: 'FeatureCollection', features: [] }
    const states = new Map((snapshot?.zones ?? []).map((z) => [z.zone_id, z]))
    return {
      type: 'FeatureCollection',
      features: geo.layers.buildings.features.map((f) => ({
        ...f,
        properties: {
          ...f.properties,
          risk_level: states.get(f.properties.zone_id)?.risk_level ?? 'LOW',
        },
      })),
    }
  }, [geo, snapshot])

  const facilityGeo = useMemo(() => {
    if (!geo?.layers?.facilities) return { type: 'FeatureCollection', features: [] }
    const threatened = new Set(
      (snapshot?.zones ?? []).flatMap((z) => z.facilities_threatened ?? []),
    )
    return {
      type: 'FeatureCollection',
      features: geo.layers.facilities.features.map((f) => ({
        ...f,
        properties: {
          ...f.properties,
          threatened: threatened.has(f.properties.name),
        },
      })),
    }
  }, [geo, snapshot])

  // Setup layers on map instance
  const setupLayers = useCallback((map) => {
    if (!map) return

    if (!map.hasImage('pulse-dot')) {
      const pulse = createPulseDot(128, map, 'rgba(244, 63, 94,')
      map.addImage('pulse-dot', pulse, { pixelRatio: 2 })
    }

    const FACILITY_ICONS = {
      'facility-hospital': { symbol: '🏥', color: '#ec4899' },
      'facility-shelter': { symbol: '🛡️', color: '#10b981' },
      'facility-fire_station': { symbol: '🚒', color: '#f97316' },
      'facility-police': { symbol: '🚓', color: '#3b82f6' },
      'facility-substation': { symbol: '⚡', color: '#eab308' },
      'facility-water_plant': { symbol: '💧', color: '#06b6d4' },
      'facility-pumping_station': { symbol: '🌊', color: '#14b8a6' },
      'facility-port': { symbol: '⚓', color: '#a855f7' },
    }

    for (const [id, cfg] of Object.entries(FACILITY_ICONS)) {
      if (!map.hasImage(id)) {
        try {
          map.addImage(id, createFacilityBadge(cfg.symbol, cfg.color), { pixelRatio: 2 })
        } catch (_) {}
      }
    }

    if (!map.hasImage('buoy-marker')) {
      try {
        map.addImage('buoy-marker', createBuoyBadge(false), { pixelRatio: 2 })
      } catch (_) {}
    }
    if (!map.hasImage('buoy-alert')) {
      try {
        map.addImage('buoy-alert', createBuoyBadge(true), { pixelRatio: 2 })
      } catch (_) {}
    }

    const empty = { type: 'FeatureCollection', features: [] }

    // 0. Verified District Boundary & Natural Coastline
    if (!map.getSource('boundary')) {
      map.addSource('boundary', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('district-boundary-fill')) {
      map.addLayer({
        id: 'district-boundary-fill',
        type: 'fill',
        source: 'boundary',
        filter: ['==', '$type', 'Polygon'],
        paint: {
          'fill-color': '#0284c7',
          'fill-opacity': 0.04,
        },
      })
    }

    if (!map.getLayer('district-boundary-casing')) {
      map.addLayer({
        id: 'district-boundary-casing',
        type: 'line',
        source: 'boundary',
        filter: ['==', '$type', 'Polygon'],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#0369a1',
          'line-width': 5.0,
          'line-opacity': 0.35,
          'line-blur': 2.5,
        },
      })
    }

    if (!map.getLayer('district-boundary-line')) {
      map.addLayer({
        id: 'district-boundary-line',
        type: 'line',
        source: 'boundary',
        filter: ['==', '$type', 'Polygon'],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#38bdf8',
          'line-width': 2.0,
          'line-dasharray': [4, 2],
          'line-opacity': 0.85,
        },
      })
    }

    if (!map.getLayer('coastline-line')) {
      map.addLayer({
        id: 'coastline-line',
        type: 'line',
        source: 'boundary',
        filter: ['==', '$type', 'LineString'],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#06b6d4',
          'line-width': 3.5,
          'line-opacity': 0.95,
          'line-blur': 0.6,
        },
      })
    }

    // 1. Exposure Radius
    if (!map.getSource('exposure-fill')) {
      map.addSource('exposure-fill', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('exposure-fill')) {
      map.addLayer({
        id: 'exposure-fill',
        type: 'fill',
        source: 'exposure-fill',
        paint: {
          'fill-color': '#f59e0b',
          'fill-opacity': 0.08,
          'fill-outline-color': 'rgba(245, 158, 11, 0.45)',
        },
      })
    }

    // 2. Hazard Sectors (Zones Fill)
    if (!map.getSource('zones-fill')) {
      map.addSource('zones-fill', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('zones-fill')) {
      map.addLayer({
        id: 'zones-fill',
        type: 'fill',
        source: 'zones-fill',
        paint: {
          'fill-color': ['case', ['get', 'selected'], '#06b6d4', RISK_MATCH],
          'fill-opacity': ['case', ['get', 'selected'], 0.28, 0.14],
        },
      })
    }

    // 3. Hydrodynamic Inundation Mesh (Flood Water Layer)
    if (!map.getSource('inundation')) {
      map.addSource('inundation', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('inundation-fill')) {
      map.addLayer({
        id: 'inundation-fill',
        type: 'fill',
        source: 'inundation',
        paint: {
          'fill-color': [
            'match', ['get', 'hazard_level'],
            'CRITICAL', '#e11d48',
            'HIGH', '#0284c7',
            'MODERATE', '#06b6d4',
            '#0ea5e9',
          ],
          'fill-opacity': [
            'match', ['get', 'hazard_level'],
            'CRITICAL', 0.58,
            'HIGH', 0.44,
            'MODERATE', 0.32,
            0.22,
          ],
        },
      })
    }

    if (!map.getLayer('inundation-line')) {
      map.addLayer({
        id: 'inundation-line',
        type: 'line',
        source: 'inundation',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#38bdf8',
          'line-width': 2.2,
          'line-blur': 0.8,
          'line-opacity': 0.85,
        },
      })
    }

    // 4. Sectors Perimeter Outline
    if (!map.getLayer('zones-line')) {
      map.addLayer({
        id: 'zones-line',
        type: 'line',
        source: 'zones-fill',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': [
            'case',
            ['get', 'selected'], '#22d3ee',
            ['get', 'isolated'], '#f43f5e',
            RISK_MATCH,
          ],
          'line-width': ['case', ['get', 'selected'], 3.2, 2.0],
          'line-dasharray': ['case', ['get', 'isolated'], ['literal', [3, 2]], ['literal', [1, 0]]],
          'line-blur': 0.5,
        },
      })
    }

    // 4b. Sector Labels
    if (!map.getLayer('zones-labels')) {
      map.addLayer({
        id: 'zones-labels',
        type: 'symbol',
        source: 'zones-fill',
        layout: {
          'text-field': ['concat', ['coalesce', ['get', 'code'], 'SEC'], ' · ', ['coalesce', ['get', 'short_name'], ['get', 'name']]],
          'text-size': 10.5,
          'text-font': ['DIN Pro Bold', 'Arial Unicode MS Bold'],
          'text-transform': 'uppercase',
          'text-letter-spacing': 0.08,
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': '#f1f5f9',
          'text-halo-color': 'rgba(10, 18, 32, 0.95)',
          'text-halo-width': 2.2,
        },
      })
    }

    // 5. Roads Underlay & Lines
    if (!map.getSource('roads')) {
      map.addSource('roads', { type: 'geojson', data: empty })
    }

    // 5a. Mapbox Native Vector Tile Arterial Network (Global Real Roads from Vector Tiles)
    if (!map.getLayer('mapbox-native-arterials') && map.getSource('composite')) {
      try {
        map.addLayer(
          {
            id: 'mapbox-native-arterials',
            source: 'composite',
            'source-layer': 'road',
            filter: [
              'in',
              ['get', 'class'],
              ['literal', ['motorway', 'trunk', 'primary', 'secondary']],
            ],
            type: 'line',
            minzoom: 9.5,
            paint: {
              'line-color': [
                'match',
                ['get', 'class'],
                'motorway', '#0284c7',
                'trunk', '#0284c7',
                'primary', '#0ea5e9',
                'secondary', '#38bdf8',
                '#334155',
              ],
              'line-width': [
                'interpolate',
                ['linear'],
                ['zoom'],
                10, 1.2,
                14, 3.2,
                16, 5.0,
              ],
              'line-opacity': 0.80,
            },
          },
          map.getLayer('zones-fill') ? 'zones-fill' : undefined,
        )
      } catch (err) {
        console.warn('mapbox-native-arterials skipped:', err)
      }
    }

    if (!map.getLayer('roads-casing')) {
      map.addLayer({
        id: 'roads-casing',
        type: 'line',
        source: 'roads',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#030712',
          'line-width': ['case', ['get', 'critical'], 5.5, 3.8],
          'line-opacity': 0.85,
        },
      })
    }

    if (!map.getLayer('roads')) {
      map.addLayer({
        id: 'roads',
        type: 'line',
        source: 'roads',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': [
            'case',
            ['!', ['get', 'passable']], '#f43f5e',
            ['get', 'is_evacuation_corridor'], '#10b981',
            '#0ea5e9',
          ],
          'line-width': [
            'case',
            ['!', ['get', 'passable']], 4.5,
            ['get', 'is_evacuation_corridor'], 4.0,
            2.8,
          ],
          'line-dasharray': ['case', ['!', ['get', 'passable']], ['literal', [3, 2]], ['literal', [1, 0]]],
          'line-opacity': 0.95,
        },
      })
    }

    if (!map.getLayer('roads-labels')) {
      map.addLayer({
        id: 'roads-labels',
        type: 'symbol',
        source: 'roads',
        minzoom: 11.5,
        layout: {
          'symbol-placement': 'line',
          'text-field': ['get', 'name'],
          'text-size': 9.5,
          'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
          'text-letter-spacing': 0.05,
          'text-max-angle': 30,
        },
        paint: {
          'text-color': [
            'case',
            ['get', 'is_evacuation_corridor'], '#34d399',
            '#f1f5f9',
          ],
          'text-halo-color': 'rgba(10, 18, 32, 0.95)',
          'text-halo-width': 2.0,
        },
      })
    }

    // 5b. Dynamic Evacuation Egress Corridors (Safe Paths to High Ground)
    if (!map.getSource('evacuation-corridors')) {
      map.addSource('evacuation-corridors', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('evac-corridors-glow')) {
      map.addLayer({
        id: 'evac-corridors-glow',
        type: 'line',
        source: 'evacuation-corridors',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#10b981',
          'line-width': 7.5,
          'line-blur': 3.5,
          'line-opacity': 0.65,
        },
      })
    }

    if (!map.getLayer('evac-corridors-line')) {
      map.addLayer({
        id: 'evac-corridors-line',
        type: 'line',
        source: 'evacuation-corridors',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#34d399',
          'line-width': 4.0,
          'line-opacity': 0.95,
        },
      })
    }

    if (!map.getLayer('evac-corridors-labels')) {
      map.addLayer({
        id: 'evac-corridors-labels',
        type: 'symbol',
        source: 'evacuation-corridors',
        minzoom: 11.0,
        layout: {
          'symbol-placement': 'line',
          'text-field': ['concat', 'SAFE EGRESS · ', ['get', 'destination_hub'], ' (', ['to-string', ['get', 'distance_km']], ' KM)'],
          'text-size': 9.5,
          'text-font': ['DIN Pro Bold', 'Arial Unicode MS Regular'],
          'text-letter-spacing': 0.08,
          'text-max-angle': 30,
        },
        paint: {
          'text-color': '#6ee7b7',
          'text-halo-color': 'rgba(6, 78, 59, 0.95)',
          'text-halo-width': 2.2,
        },
      })
    }

    // 5c. Topological Bottlenecks & Bridge Cut-Edge Markers
    if (!map.getSource('bottlenecks')) {
      map.addSource('bottlenecks', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('bottlenecks-glow')) {
      map.addLayer({
        id: 'bottlenecks-glow',
        type: 'circle',
        source: 'bottlenecks',
        paint: {
          'circle-radius': ['case', ['get', 'defended'], 14, 18],
          'circle-color': [
            'case',
            ['get', 'defended'], 'rgba(16, 185, 129, 0.35)',
            ['==', ['get', 'status'], 'SEVERED'], 'rgba(244, 63, 94, 0.45)',
            'rgba(245, 158, 11, 0.45)',
          ],
          'circle-stroke-color': [
            'case',
            ['get', 'defended'], '#10b981',
            ['==', ['get', 'status'], 'SEVERED'], '#f43f5e',
            '#f59e0b',
          ],
          'circle-stroke-width': 2.0,
        },
      })
    }

    if (!map.getLayer('bottlenecks-core')) {
      map.addLayer({
        id: 'bottlenecks-core',
        type: 'circle',
        source: 'bottlenecks',
        paint: {
          'circle-radius': 7.0,
          'circle-color': [
            'case',
            ['get', 'defended'], '#10b981',
            ['==', ['get', 'status'], 'SEVERED'], '#f43f5e',
            '#f59e0b',
          ],
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 1.5,
        },
      })
    }

    if (!map.getLayer('bottlenecks-labels')) {
      map.addLayer({
        id: 'bottlenecks-labels',
        type: 'symbol',
        source: 'bottlenecks',
        minzoom: 11.5,
        layout: {
          'text-field': [
            'concat',
            ['get', 'ref'],
            ' · ',
            ['case', ['get', 'defended'], 'DEFENDED', ['==', ['get', 'status'], 'SEVERED'], 'SEVERED CUT-EDGE', 'BOTTLENECK'],
          ],
          'text-size': 9.5,
          'text-font': ['DIN Pro Bold', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.4],
          'text-anchor': 'top',
        },
        paint: {
          'text-color': [
            'case',
            ['get', 'defended'], '#34d399',
            ['==', ['get', 'status'], 'SEVERED'], '#fda4af',
            '#fef08a',
          ],
          'text-halo-color': 'rgba(10, 18, 32, 0.95)',
          'text-halo-width': 2.2,
        },
      })
    }

    // 6. Native Mapbox 3D Buildings (Whole City Architectural Scale)
    if (!map.getLayer('3d-buildings-osm') && map.getSource('composite')) {
      const allLayers = map.getStyle().layers || []
      const labelLayerId = allLayers.find(
        (l) => l.type === 'symbol' && l.layout && l.layout['text-field']
      )?.id

      try {
        map.addLayer(
          {
            id: '3d-buildings-osm',
            source: 'composite',
            'source-layer': 'building',
            filter: ['==', 'extrude', 'true'],
            type: 'fill-extrusion',
            minzoom: 12,
            paint: {
              'fill-extrusion-color': [
                'interpolate',
                ['linear'],
                ['get', 'height'],
                0, '#0f172a',
                20, '#1e293b',
                50, '#334155',
              ],
              'fill-extrusion-height': [
                'interpolate',
                ['linear'],
                ['zoom'],
                12, 0,
                12.5, ['coalesce', ['get', 'height'], 15],
              ],
              'fill-extrusion-base': [
                'interpolate',
                ['linear'],
                ['zoom'],
                12, 0,
                12.5, ['coalesce', ['get', 'min_height'], 0],
              ],
              'fill-extrusion-opacity': 0.65,
            },
          },
          labelLayerId,
        )
      } catch (err) {
        console.warn('3d-buildings-osm skipped:', err)
      }
    }

    // 7. Tactical Building Parcels (Facility Extrusions)
    if (!map.getSource('buildings-3d')) {
      map.addSource('buildings-3d', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('buildings-3d')) {
      map.addLayer({
        id: 'buildings-3d',
        type: 'fill-extrusion',
        source: 'buildings-3d',
        paint: {
          'fill-extrusion-color': [
            'match', ['get', 'use'],
            'hospital', '#ec4899',
            'shelter', '#10b981',
            'fire_station', '#f97316',
            'police', '#3b82f6',
            'substation', '#eab308',
            'water_plant', '#06b6d4',
            'pumping_station', '#14b8a6',
            'port', '#a855f7',
            '#38bdf8',
          ],
          'fill-extrusion-height': ['coalesce', ['get', 'height_m'], 16],
          'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.88,
        },
      })
    }

    // 8. What-If Trajectory
    if (!map.getLayer('sim-line')) {
      map.addLayer({
        id: 'sim-line',
        type: 'line',
        source: { type: 'geojson', data: empty },
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#c084fc', 'line-width': 3, 'line-dasharray': [2, 1.5] },
      })
    }

    if (!map.getLayer('sim-points')) {
      map.addLayer({
        id: 'sim-points',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': 5.5,
          'circle-color': '#c084fc',
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 1.5,
        },
      })
    }

    // 9. Coastal Assets
    if (!map.getSource('assets')) {
      map.addSource('assets', { type: 'geojson', data: empty })
    }
    if (!map.getLayer('assets')) {
      map.addLayer({
        id: 'assets',
        type: 'circle',
        source: 'assets',
        paint: {
          'circle-radius': 4.5,
          'circle-color': '#94a3b8',
          'circle-opacity': 0.75,
        },
      })
    }

    // 10. Critical Facilities — Native Compact Mapbox Symbols
    if (!map.getSource('facilities')) {
      map.addSource('facilities', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('facilities')) {
      map.addLayer({
        id: 'facilities',
        type: 'symbol',
        source: 'facilities',
        layout: {
          'icon-image': [
            'match',
            ['get', 'kind'],
            'hospital', 'facility-hospital',
            'shelter', 'facility-shelter',
            'fire_station', 'facility-fire_station',
            'police', 'facility-police',
            'substation', 'facility-substation',
            'water_plant', 'facility-water_plant',
            'pumping_station', 'facility-pumping_station',
            'port', 'facility-port',
            'facility-shelter',
          ],
          'icon-size': 0.40,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      })
    }

    if (!map.getLayer('facilities-labels')) {
      map.addLayer({
        id: 'facilities-labels',
        type: 'symbol',
        source: 'facilities',
        minzoom: 15.0,
        layout: {
          'text-field': ['get', 'short_label'],
          'text-size': 9.5,
          'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.25],
          'text-anchor': 'top',
          'text-allow-overlap': false,
          'text-optional': true,
        },
        paint: {
          'text-color': '#f8fafc',
          'text-halo-color': 'rgba(11, 21, 38, 0.95)',
          'text-halo-width': 2.2,
        },
      })
    }

    // 11. Sensors & Offshore Marine Buoys
    if (!map.getSource('sensors')) {
      map.addSource('sensors', { type: 'geojson', data: empty })
    }

    if (!map.getLayer('sensors-beacon')) {
      map.addLayer({
        id: 'sensors-beacon',
        type: 'circle',
        source: 'sensors',
        paint: {
          'circle-radius': ['case', ['get', 'anomalous'], 14, 11],
          'circle-color': ['case', ['get', 'anomalous'], 'rgba(244, 63, 94, 0.35)', 'rgba(6, 182, 212, 0.22)'],
          'circle-stroke-color': ['case', ['get', 'anomalous'], '#f43f5e', '#06b6d4'],
          'circle-stroke-width': 1.6,
        },
      })
    }

    if (!map.getLayer('sensors')) {
      map.addLayer({
        id: 'sensors',
        type: 'symbol',
        source: 'sensors',
        layout: {
          'icon-image': ['case', ['get', 'anomalous'], 'buoy-alert', 'buoy-marker'],
          'icon-size': 0.42,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      })
    }

    if (!map.getLayer('sensors-labels')) {
      map.addLayer({
        id: 'sensors-labels',
        type: 'symbol',
        source: 'sensors',
        minzoom: 10.5,
        layout: {
          'text-field': [
            'concat',
            ['get', 'name'],
            '\n~ ',
            ['coalesce', ['to-string', ['get', 'wave_height_m']], '1.2'],
            'm swell · ',
            ['coalesce', ['to-string', ['get', 'temperature']], '--'],
            '°C',
          ],
          'text-size': 9.5,
          'text-font': ['DIN Pro Bold', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.45],
          'text-anchor': 'top',
          'text-allow-overlap': false,
          'text-optional': true,
        },
        paint: {
          'text-color': '#38bdf8',
          'text-halo-color': 'rgba(11, 21, 38, 0.95)',
          'text-halo-width': 2.4,
        },
      })
    }

    // 12. SOS Distress Beacons
    if (!map.getSource('sos')) {
      map.addSource('sos', { type: 'geojson', data: empty })
    }
    if (!map.getLayer('sos')) {
      map.addLayer({
        id: 'sos',
        type: 'circle',
        source: 'sos',
        paint: {
          'circle-radius': 11,
          'circle-color': ['case', ['==', ['get', 'status'], 'RESCUED'], '#10b981', '#ffffff'],
          'circle-stroke-color': '#f43f5e',
          'circle-stroke-width': 2.8,
        },
      })
    }

    // 13. Event Epicenters
    if (!map.getSource('events')) {
      map.addSource('events', { type: 'geojson', data: empty })
    }
    if (!map.getLayer('events')) {
      map.addLayer({
        id: 'events',
        type: 'symbol',
        source: 'events',
        layout: {
          'icon-image': 'pulse-dot',
          'icon-size': 0.30,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      })
    }

    // Add Terrain & Atmospheric Fog
    if (hasValidToken) {
      try {
        if (!map.getSource('mapbox-dem')) {
          map.addSource('mapbox-dem', {
            type: 'raster-dem',
            url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
            tileSize: 512,
            maxzoom: 14,
          })
        }
        map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.25 })
        map.setFog({
          range: [-1, 2],
          'horizon-blend': 0.25,
          color: '#050a14',
          'high-color': '#0f1c31',
          'space-color': '#02050b',
        })
      } catch (err) {
        console.warn('Terrain/fog configuration skipped:', err)
      }
    }

    // Interactive Popups
    const showFacilityPopup = (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">${p.name}</div>
           <div class="popup-row"><span>Classification</span><strong>${(p.kind || '').replace('_', ' ').toUpperCase()}</strong></div>
           <div class="popup-row"><span>Service Type</span><strong>${p.service_type || 'Emergency Support'}</strong></div>
           <div class="popup-row"><span>Sector</span><strong>Sector ${p.zone_id}</strong></div>
           <div class="popup-row"><span>Elevation</span><strong>${p.elevation_m != null ? p.elevation_m + ' m MSL' : '—'}</strong></div>
           <div class="popup-row"><span>Capacity</span><strong>${p.capacity || '—'}</strong></div>
           <div class="popup-row"><span>Status</span><strong class="${p.threatened ? 'alert' : 'status-ok'}">${p.threatened ? '⚠️ FLOOD THREATENED' : '✅ FULLY OPERATIONAL'}</strong></div>`,
        )
        .addTo(map)
    }

    map.on('click', 'facilities', showFacilityPopup)
    map.on('click', 'facilities-labels', showFacilityPopup)

    map.on('click', 'zones-fill', (e) => {
      const p = e.features[0]?.properties
      if (p?.id) selectZone(p.id)
    })

    const showRoadPopup = (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 12 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">🛣️ ${p.name}</div>
           <div class="popup-row"><span>Classification</span><strong>${(p.classification || 'Arterial Highway').replace('_', ' ').toUpperCase()}</strong></div>
           <div class="popup-row"><span>Deck Elevation</span><strong>${p.elevation_m != null ? p.elevation_m + ' m MSL' : '—'}</strong></div>
           <div class="popup-row"><span>Capacity</span><strong>${p.lanes || 4} lanes (${p.speed_limit_kmh ? p.speed_limit_kmh + ' km/h' : 'Standard'})</strong></div>
           ${p.is_cut_edge ? `<div class="popup-row"><span>Topological Cut-Edge</span><strong class="alert">⚠️ CHOKEPOINT (${Number(p.betweenness_centrality).toFixed(3)})</strong></div>` : ''}
           ${p.defended ? `<div class="popup-row"><span>Physical Defense</span><strong class="status-ok">🛡️ HIGH-CAPACITY PUMPS ACTIVE</strong></div>` : ''}
           <div class="popup-row"><span>Evacuation Egress</span><strong>${p.is_evacuation_corridor ? '🟢 DESIGNATED EVACUATION CORRIDOR' : 'Standard Highway Route'}</strong></div>
           <div class="popup-row"><span>Accessibility</span><strong class="${p.passable ? 'status-ok' : 'alert'}">${p.passable ? '✅ PASSABLE' : `⚠️ SUBMERGED (+${p.submersion_m}m)`}</strong></div>`,
        )
        .addTo(map)
    }

    map.on('click', 'roads', showRoadPopup)
    map.on('click', 'roads-labels', showRoadPopup)

    const showBottleneckPopup = (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      const isDefended = Boolean(p.defended)
      const popup = new mapboxgl.Popup({ closeButton: true, offset: 14 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">⚡ ${p.name}</div>
           <div class="popup-row"><span>Classification</span><strong>${(p.classification || 'Arterial Highway').replace('_', ' ').toUpperCase()}</strong></div>
           <div class="popup-row"><span>Highway Corridor</span><strong>${p.ref || 'Arterial'}</strong></div>
           <div class="popup-row"><span>Centrality Chokepoint</span><strong>${Number(p.betweenness_centrality).toFixed(3)} ${p.is_cut_edge ? '(Cut-Edge)' : ''}</strong></div>
           <div class="popup-row"><span>Deck MSL / Water</span><strong>${p.deck_elevation_m}m / +${p.water_on_deck_m}m</strong></div>
           <div class="popup-row"><span>Isolated Population</span><strong>${Number(p.isolated_population || 35000).toLocaleString()} residents</strong></div>
           <div class="popup-row"><span>Defense Status</span><strong class="${isDefended ? 'status-ok' : p.status === 'SEVERED' ? 'alert' : 'status-mod'}">${isDefended ? '🛡️ ACTIVE PUMP DEFENSE' : p.status === 'SEVERED' ? '⚠️ SEVERED CUT-EDGE' : '⚠️ THREATENED'}</strong></div>
           <button id="topo-popup-btn-${p.id}" style="width:100%; margin-top:10px; padding:7px 12px; background:${isDefended ? '#10b981' : '#f59e0b'}; color:#fff; border:none; border-radius:4px; font-weight:bold; cursor:pointer; font-family:monospace; font-size:11px;">
             ${isDefended ? '🛡️ STAND DOWN DEFENSE' : '⚡ AUTHORIZE DEWATERING PUMPS'}
           </button>`
        )
        .addTo(map)

      setTimeout(() => {
        const btn = document.getElementById(`topo-popup-btn-${p.id}`)
        if (btn) {
          btn.onclick = async () => {
            btn.innerText = 'COMMUNICATING...'
            await useTidalis.getState().authorizeBottleneckDefense(p.id)
            popup.remove()
          }
        }
      }, 50)
    }

    map.on('click', 'bottlenecks-glow', showBottleneckPopup)
    map.on('click', 'bottlenecks-core', showBottleneckPopup)
    map.on('click', 'bottlenecks-labels', showBottleneckPopup)

    map.on('click', 'inundation-fill', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 14 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">🌊 ${p.name || 'Hydrodynamic Flood Inundation'}</div>
           <div class="popup-row"><span>Water Depth</span><strong>${p.depth_m != null ? p.depth_m + ' m' : '—'}</strong></div>
           <div class="popup-row"><span>Hazard Tier</span><strong class="alert">${p.hazard_level || 'CRITICAL'}</strong></div>`,
        )
        .addTo(map)
    })

    map.on('click', 'events', (e) => {
      const id = e.features[0]?.properties?.id
      if (id) selectEvent(id)
    })

    map.on('click', 'buildings-3d', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 15 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">🏢 ${p.name || 'Tactical Facility Campus'}</div>
           <div class="popup-row"><span>Function</span><strong>${(p.use || 'public_service').toUpperCase()}</strong></div>
           <div class="popup-row"><span>Height</span><strong>${p.height_m || 16} m</strong></div>`,
        )
        .addTo(map)
    })

    const showSensorPopup = (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">⚓ ${p.name}</div>
           <div class="popup-row"><span>Station ID</span><strong>${p.id}</strong></div>
           <div class="popup-row"><span>Station Type</span><strong>${(p.sensor_type || 'marine_buoy').replace('_', ' ').toUpperCase()}</strong></div>
           <div class="popup-row"><span>Wave Swell</span><strong style="color: #38bdf8">${p.wave_height_m != null ? p.wave_height_m + ' m' : '—'}</strong></div>
           <div class="popup-row"><span>Sea Surface Temp</span><strong>${p.temperature != null ? p.temperature + ' °C' : '—'}</strong></div>
           <div class="popup-row"><span>Water Level / Surge</span><strong>+${p.water_level_m != null ? p.water_level_m + ' m' : '0.85 m'}</strong></div>
           <div class="popup-row"><span>Turbidity</span><strong>${p.turbidity != null ? p.turbidity + ' NTU' : '—'}</strong></div>
           <div class="popup-row"><span>Dissolved O₂</span><strong>${p.dissolved_oxygen != null ? p.dissolved_oxygen + ' mg/L' : '—'}</strong></div>
           <div class="popup-row"><span>Telemetry Status</span><strong style="color: #10b981">LIVE · TRANSMITTING</strong></div>`,
        )
        .addTo(map)
    }

    map.on('click', 'sensors', showSensorPopup)
    map.on('click', 'sensors-beacon', showSensorPopup)
    map.on('click', 'sensors-labels', showSensorPopup)

    map.on('click', 'sos', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">🆘 SOS: ${p.name}</div>
           <div class="popup-row"><span>ID</span><strong>${p.id}</strong></div>
           <div class="popup-row"><span>Urgency</span><strong class="${p.urgency === 'CRITICAL' ? 'alert' : ''}">${p.urgency}</strong></div>
           <div class="popup-row"><span>Status</span><strong>${p.status}</strong></div>
           <div class="popup-row"><span>Rescue Method</span><strong>${(p.method || '').replace('_', ' ')}</strong></div>`,
        )
        .addTo(map)
    })

    // Cursor pointer on interactive items
    for (const layerId of ['events', 'zones-fill', 'inundation-fill', 'roads', 'roads-labels', 'sos', 'facilities', 'facilities-labels', 'buildings-3d', 'sensors', 'sensors-beacon', 'sensors-labels', 'assets']) {
      map.on('mouseenter', layerId, () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', layerId, () => {
        map.getCanvas().style.cursor = ''
      })
    }
  }, [hasValidToken, selectZone, selectEvent])

  // ---------- Init Mapbox ----------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current || !hasValidToken) return

    mapboxgl.accessToken = mapboxToken

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: currentStyleUrl,
      center: centerCoords,
      zoom: DEFAULT_ZOOM,
      pitch: 48,
      bearing: -12,
      attributionControl: true,
      antialias: true,
    })

    map.on('error', (e) => {
      console.warn('Mapbox notification:', e?.error?.message || e)
    })

    mapRef.current = map
    if (typeof window !== 'undefined') window._mapboxMap = map

    const geolocate = new mapboxgl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: false,
      showUserHeading: true,
    })

    geolocate.on('geolocate', (pos) => {
      if (pos?.coords) {
        const lat = Number(pos.coords.latitude.toFixed(4))
        const lon = Number(pos.coords.longitude.toFixed(4))
        useTidalis.getState().setLocation(lat, lon, 'Live GPS Position')
      }
    })

    map.addControl(geolocate, 'bottom-right')

    map.on('load', () => {
      setupLayers(map)
      setReady(true)
    })

    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current) {
        mapRef.current.resize()
      }
    })
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasValidToken, mapboxToken, currentStyleUrl, setupLayers])

  // ---------- Style update ---------------------------------------------------
  const prevStyleRef = useRef(currentStyleUrl)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (prevStyleRef.current === currentStyleUrl) return

    prevStyleRef.current = currentStyleUrl
    if (hasValidToken) {
      mapboxgl.accessToken = mapboxToken
    }

    setReady(false)
    map.setStyle(currentStyleUrl)
    map.once('style.load', () => {
      setupLayers(map)
      setReady(true)
    })
  }, [currentStyleUrl, hasValidToken, mapboxToken, setupLayers, ready])

  // ---------- Layer visibility sync -----------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    for (const [lid, isOn] of [
      ['district-boundary-fill', layers.zones],
      ['district-boundary-casing', layers.zones],
      ['district-boundary-line', layers.zones],
      ['coastline-line', layers.zones],
      ['sensors', layers.sensors],
      ['sensors-beacon', layers.sensors],
      ['sensors-labels', layers.sensors],
      ['events', layers.events],
      ['exposure-fill', layers.exposure],
      ['sim-line', layers.simulation],
      ['sim-points', layers.simulation],
      ['assets', layers.exposure],
      ['sos', layers.sos],
      ['zones-fill', layers.zones],
      ['zones-line', layers.zones],
      ['zones-labels', layers.zones],
      ['inundation-fill', layers.flood],
      ['inundation-line', layers.flood],
      ['roads', layers.roads],
      ['roads-casing', layers.roads],
      ['roads-labels', layers.roads],
      ['mapbox-native-arterials', layers.roads],
      ['evac-corridors-glow', layers.roads],
      ['evac-corridors-line', layers.roads],
      ['evac-corridors-labels', layers.roads],
      ['bottlenecks-glow', layers.roads],
      ['bottlenecks-core', layers.roads],
      ['bottlenecks-labels', layers.roads],
      ['buildings-3d', layers.buildings],
      ['3d-buildings-osm', layers.buildings],
      ['facilities', layers.facilities],
      ['facilities-labels', layers.facilities],
    ]) {
      if (map.getLayer(lid)) {
        map.setLayoutProperty(lid, 'visibility', isOn ? 'visible' : 'none')
      }
    }
  }, [layers, ready])

  // ---------- Data sync ------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    for (const [lid, geojson] of [
      ['boundary', boundaryGeo],
      ['sensors', sensorGeo],
      ['events', eventGeo],
      ['exposure-fill', exposureGeo],
      ['assets', assetGeo],
      ['sos', sosGeo],
      ['zones-fill', zoneGeo],
      ['inundation', inundationGeo],
      ['roads', roadGeo],
      ['evacuation-corridors', evacCorridorGeo],
      ['bottlenecks', bottleneckGeo],
      ['buildings-3d', buildingGeo],
      ['facilities', facilityGeo],
    ]) {
      const source = map.getSource(lid)
      if (source && typeof source.setData === 'function') {
        source.setData(geojson)
      }
    }
  }, [ready, boundaryGeo, sensorGeo, eventGeo, exposureGeo, assetGeo, sosGeo, zoneGeo, inundationGeo, roadGeo, evacCorridorGeo, bottleneckGeo, buildingGeo, facilityGeo])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.getSource('sim-line')?.setData(simulationGeo)
    map.getSource('sim-points')?.setData(simulationGeo)
  }, [ready, simulationGeo])

  // ---------- Fly to mapTarget on demand -------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !mapTarget) return
    const targetLon = mapTarget.lng ?? mapTarget.lon
    const targetLat = mapTarget.lat
    if (targetLon == null || targetLat == null) return
    map.flyTo({
      center: [targetLon, targetLat],
      zoom: mapTarget.zoom ?? 15,
      pitch: mapTarget.pitch ?? 45,
      bearing: mapTarget.bearing ?? 0,
      duration: 1800,
      essential: true,
    })
  }, [mapTarget, ready])

  // ---------- Fly to selected event ------------------------------------------
  const prevSelectedEventRef = useRef(null)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !selectedEventId) return
    if (prevSelectedEventRef.current !== null && prevSelectedEventRef.current !== selectedEventId) {
      const evt = events.find((e) => e.event_id === selectedEventId)
      if (evt) {
        map.flyTo({
          center: [evt.longitude, evt.latitude],
          zoom: Math.max(map.getZoom(), 12.5),
          duration: 1200,
          essential: true,
        })
      }
    }
    prevSelectedEventRef.current = selectedEventId
    loadExposures()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, selectedEventId])

  // ---------- Fly to operational theater when geo updates -------------------
  const prevGeoBboxRef = useRef(null)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    const bbox = geo?.meta?.bbox
    if (bbox && Array.isArray(bbox) && bbox.length === 4) {
      const bboxKey = bbox.map((v) => Number(v).toFixed(3)).join(',')
      if (prevGeoBboxRef.current !== bboxKey) {
        prevGeoBboxRef.current = bboxKey
        try {
          const container = map.getContainer()
          if (container && container.clientWidth > 100 && container.clientHeight > 100) {
            map.fitBounds(
              [
                [bbox[0], bbox[1]],
                [bbox[2], bbox[3]],
              ],
              {
                padding: { top: 20, bottom: 20, left: 20, right: 20 },
                duration: 1200,
                essential: true,
              },
            )
          } else {
            const p = geo?.meta?.center || [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
            map.flyTo({ center: p, zoom: DEFAULT_ZOOM, duration: 1100, essential: true })
          }
        } catch {
          const p = geo?.meta?.center || [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
          map.flyTo({ center: p, zoom: DEFAULT_ZOOM, duration: 1100, essential: true })
        }
      }
      return
    }

    const p = geo?.meta?.center || geo?.layers?.zones?.features?.[0]?.geometry?.coordinates?.[0]?.[0]
    if (p && p.length === 2) {
      const key = `${p[0].toFixed(2)},${p[1].toFixed(2)}`
      if (prevGeoBboxRef.current !== key) {
        prevGeoBboxRef.current = key
        map.flyTo({ center: [p[0], p[1]], zoom: DEFAULT_ZOOM, duration: 1100, essential: true })
      }
    }
  }, [ready, geo])

  // ---------- Camera controls ------------------------------------------------
  const toggle3D = () => {
    const map = mapRef.current
    if (!map) return
    if (pitched) {
      map.easeTo({ pitch: 0, bearing: 0, duration: 800 })
      setPitched(false)
    } else {
      map.easeTo({ pitch: 56, bearing: -14, duration: 900 })
      setPitched(true)
    }
  }

  const handleRecenter = () => {
    const map = mapRef.current
    if (!map) return

    const bbox = geo?.meta?.bbox
    if (bbox && Array.isArray(bbox) && bbox.length === 4) {
      try {
        const container = map.getContainer()
        if (container && container.clientWidth > 100 && container.clientHeight > 100) {
          map.fitBounds(
            [
              [bbox[0], bbox[1]],
              [bbox[2], bbox[3]],
            ],
            {
              padding: { top: 20, bottom: 20, left: 20, right: 20 },
              duration: 1000,
              essential: true,
            },
          )
        } else {
          const targetCenter = geo?.meta?.center || centerCoords
          map.flyTo({ center: targetCenter, zoom: DEFAULT_ZOOM, duration: 900, essential: true })
        }
      } catch {
        const targetCenter = geo?.meta?.center || centerCoords
        map.flyTo({ center: targetCenter, zoom: DEFAULT_ZOOM, duration: 900, essential: true })
      }
      return
    }

    const targetCenter = geo?.meta?.center || centerCoords
    map.flyTo({ center: targetCenter, zoom: DEFAULT_ZOOM, duration: 900, essential: true })
  }

  const handleFlyToUser = () => {
    const map = mapRef.current
    if (!map || !userLocation?.lat || !userLocation?.lon) return
    map.flyTo({ center: [userLocation.lon, userLocation.lat], zoom: 13.0, duration: 900, essential: true })
  }

  return (
    <div className="map-viewport">
      {!hasValidToken ? (
        <div className="mapbox-activation-container">
          <div className="mapbox-activation-card">
            <div className="activation-badge">API CONFIGURATION</div>
            <div className="activation-icon">🗺️</div>
            <h2 className="activation-title">Mapbox GL Engine Activation</h2>
            <p className="activation-desc">
              TIDALIS Digital Twin operates on <strong>Mapbox GL JS v3</strong> for hardware-accelerated 3D coastal topography, dynamic flood polygons, and bathymetric imagery.
            </p>
            <form onSubmit={handleActivate} className="activation-form">
              <label className="activation-label">Enter Mapbox Public Access Token:</label>
              <div className="activation-input-row">
                <input
                  type="text"
                  placeholder="pk.eyJ1..."
                  value={inputToken}
                  onChange={(e) => setInputToken(e.target.value)}
                  className="activation-input"
                  autoFocus
                />
                <button type="submit" className="activation-submit-btn">
                  Launch Map
                </button>
              </div>
              {tokenError && <div className="activation-error">{tokenError}</div>}
            </form>
            <div className="activation-links">
              <a
                href="https://account.mapbox.com/access-tokens/"
                target="_blank"
                rel="noreferrer"
                className="activation-link"
              >
                Get a free token at mapbox.com ↗ (Free 50,000 monthly loads)
              </a>
              <div className="activation-note">
                Or add <code>VITE_MAPBOX_TOKEN=pk.ey...</code> to <code>frontend/.env</code>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="map-canvas-container" ref={containerRef} />

          {/* Floating HUD Controls */}
          <MapHUD
            pitched={pitched}
            onToggle3D={toggle3D}
            onRecenter={handleRecenter}
            onFlyToUser={handleFlyToUser}
          />

          {/* Collapsible Floating Legend */}
          <MapLegend />
        </>
      )}
    </div>
  )
}
