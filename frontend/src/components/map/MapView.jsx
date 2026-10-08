import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { useTidalis } from '../../store'
import MapHUD from './MapHUD'
import MapLegend from './MapLegend'
import { MAPBOX_STYLES, RISK_MATCH, circlePolygon } from './mapboxStyles'
import { createPulseDot } from './pulseMarker'

const DEFAULT_ZOOM = 11.2

export default function MapView() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [pitched, setPitched] = useState(false)
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

  const centerCoords = useMemo(() => {
    if (userLocation?.lon && userLocation?.lat) return [userLocation.lon, userLocation.lat]
    if (activeLocation?.lon && activeLocation?.lat) return [activeLocation.lon, activeLocation.lat]
    return [73.97, 15.30]
  }, [userLocation, activeLocation])

  const geo = useTidalis((s) => s.geo)
  const snapshot = useTidalis((s) => s.snapshot)
  const selectZone = useTidalis((s) => s.selectZone)
  const selectedZoneId = useTidalis((s) => s.selectedZoneId)

  // Determine current active style URL & token
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
      const anomalous = (r.turbidity ?? 0) > 20 || (r.temperature ?? 0) > 30.5
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.longitude, s.latitude] },
        properties: {
          id: s.sensor_id,
          name: s.name,
          anomalous: Boolean(anomalous),
          temperature: r.temperature,
          turbidity: r.turbidity,
          ph: r.ph,
          dissolved_oxygen: r.dissolved_oxygen,
        },
      }
    })
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
        },
      })),
    }),
    [events],
  )

  const exposureGeo = useMemo(() => {
    const event = events.find((e) => e.event_id === selectedEventId)
    if (!event) return { type: 'FeatureCollection', features: [] }
    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: circlePolygon(event.longitude, event.latitude, event.radius_km),
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

  const sosTickets = useTidalis((s) => s.sosTickets)
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
            color: state?.risk_color ?? '#34d399',
            isolated: isolated.has(f.properties.id),
            selected: f.properties.id === selectedZoneId,
          },
        }
      }),
    }
  }, [geo, snapshot, selectedZoneId])

  const roadGeo = useMemo(() => {
    if (!geo?.layers?.roads) return { type: 'FeatureCollection', features: [] }
    const blocked = new Map(
      (snapshot?.isolation?.blocked_roads ?? []).map((r) => [r.id, r]),
    )
    return {
      type: 'FeatureCollection',
      features: geo.layers.roads.features.map((f) => {
        const status = blocked.get(f.properties.id)
        return {
          ...f,
          properties: {
            ...f.properties,
            passable: !status,
            submersion_m: status?.submersion_m ?? 0,
          },
        }
      }),
    }
  }, [geo, snapshot])

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

    // Pulse dot image for events
    if (!map.hasImage('pulse-dot')) {
      const pulse = createPulseDot(128, map)
      map.addImage('pulse-dot', pulse, { pixelRatio: 2 })
    }

    const empty = { type: 'FeatureCollection', features: [] }

    // 1. Exposure Fill
    if (!map.getLayer('exposure-fill')) {
      map.addLayer({
        id: 'exposure-fill',
        type: 'fill',
        source: { type: 'geojson', data: empty },
        paint: {
          'fill-color': '#fbbf24',
          'fill-opacity': 0.12,
          'fill-outline-color': 'rgba(251,191,36,0.6)',
        },
      })
    }

    // 2. Zones Fill
    if (!map.getLayer('zones-fill')) {
      map.addLayer({
        id: 'zones-fill',
        type: 'fill',
        source: { type: 'geojson', data: empty },
        paint: {
          'fill-color': ['case', ['get', 'selected'], '#22d3ee', RISK_MATCH],
          'fill-opacity': [
            '+',
            0.15,
            ['*', ['min', ['get', 'flood_depth_m'], 2.5], 0.20],
          ],
        },
      })
    }

    // 3. Flood Water Layer
    if (!map.getLayer('flood-fill')) {
      map.addLayer({
        id: 'flood-fill',
        type: 'fill',
        source: { type: 'geojson', data: empty },
        paint: {
          'fill-color': '#0ea5e9',
          'fill-opacity': [
            'case',
            ['>', ['get', 'flood_depth_m'], 0.02],
            ['*', ['min', ['get', 'flood_depth_m'], 2.5], 0.35],
            0,
          ],
          'fill-outline-color': 'rgba(34,211,238,0.7)',
        },
      })
    }

    // 4. Zones Line
    if (!map.getLayer('zones-line')) {
      map.addLayer({
        id: 'zones-line',
        type: 'line',
        source: { type: 'geojson', data: empty },
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': [
            'case',
            ['get', 'isolated'], '#fb7185',
            ['get', 'selected'], '#22d3ee',
            RISK_MATCH,
          ],
          'line-width': ['case', ['get', 'selected'], 3.2, 1.8],
          'line-dasharray': ['case', ['get', 'isolated'], ['literal', [2, 1.2]], ['literal', [1, 0]]],
        },
      })
    }

    // 5. Roads
    if (!map.getLayer('roads')) {
      map.addLayer({
        id: 'roads',
        type: 'line',
        source: { type: 'geojson', data: empty },
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['case', ['get', 'passable'], '#3b82f6', '#fb7185'],
          'line-width': [
            'case',
            ['get', 'passable'], ['case', ['get', 'critical'], 3.5, 2.2],
            ['case', ['get', 'critical'], 4.8, 3.4],
          ],
          'line-opacity': 0.95,
          'line-blur': 0.3,
        },
      })
    }

    // 6. 3D Extruded Buildings
    if (!map.getLayer('buildings-3d')) {
      map.addLayer({
        id: 'buildings-3d',
        type: 'fill-extrusion',
        source: { type: 'geojson', data: empty },
        paint: {
          'fill-extrusion-color': [
            'match', ['get', 'risk_level'],
            'CRITICAL', '#7f1d2e',
            'HIGH', '#7c4a12',
            'MODERATE', '#6b5410',
            '#1d3a55',
          ],
          'fill-extrusion-height': ['get', 'height_m'],
          'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.78,
        },
      })
    }

    // 7. What-If Trajectory Line
    if (!map.getLayer('sim-line')) {
      map.addLayer({
        id: 'sim-line',
        type: 'line',
        source: { type: 'geojson', data: empty },
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#c084fc', 'line-width': 3, 'line-dasharray': [2, 1.5] },
      })
    }

    // 8. What-If Points
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

    // 9. Assets
    if (!map.getLayer('assets')) {
      map.addLayer({
        id: 'assets',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': 4.5,
          'circle-color': '#64748b',
          'circle-opacity': 0.75,
        },
      })
    }

    // 10. Critical Facilities
    if (!map.getLayer('facilities')) {
      map.addLayer({
        id: 'facilities',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': ['case', ['get', 'threatened'], 8.5, 6.5],
          'circle-color': ['case', ['get', 'threatened'], '#fb7185', '#22d3ee'],
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 1.6,
        },
      })
    }

    // 11. Sensors
    if (!map.getLayer('sensors')) {
      map.addLayer({
        id: 'sensors',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': ['case', ['get', 'anomalous'], 9, 6],
          'circle-color': ['case', ['get', 'anomalous'], '#fb7185', '#38bdf8'],
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 1.4,
        },
      })
    }

    // 12. SOS Distress Beacons
    if (!map.getLayer('sos')) {
      map.addLayer({
        id: 'sos',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': 11,
          'circle-color': ['case', ['==', ['get', 'status'], 'RESCUED'], '#34d399', '#ffffff'],
          'circle-stroke-color': '#fb7185',
          'circle-stroke-width': 2.5,
        },
      })
    }

    // 13. Event Epicenters
    if (!map.getLayer('events')) {
      map.addLayer({
        id: 'events',
        type: 'symbol',
        source: { type: 'geojson', data: empty },
        layout: {
          'icon-image': 'pulse-dot',
          'icon-size': 0.25,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      })
    }

    // Add Terrain & Atmospheric Fog if using Mapbox styles
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

    // Interactive Click Handlers
    map.on('click', 'zones-fill', (e) => {
      const id = e.features[0]?.properties?.id
      if (id) selectZone(id)
    })

    map.on('click', 'events', (e) => {
      const id = e.features[0]?.properties?.id
      if (id) selectEvent(id)
    })

    map.on('click', 'facilities', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">${p.name}</div>
           <div class="popup-row"><span>Type</span><strong>${p.kind}</strong></div>
           <div class="popup-row"><span>Zone</span><strong>${p.zone_id}</strong></div>
           <div class="popup-row"><span>Status</span><strong class="${p.threatened ? 'alert' : ''}">${p.threatened ? 'THREATENED' : 'clear'}</strong></div>`,
        )
        .addTo(map)
    })

    map.on('click', 'sensors', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">${p.name}</div>
           <div class="popup-row"><span>Sensor</span><strong>${p.id}</strong></div>
           <div class="popup-row"><span>Temperature</span><strong>${p.temperature ?? '—'} °C</strong></div>
           <div class="popup-row"><span>Turbidity</span><strong>${p.turbidity ?? '—'} NTU</strong></div>
           <div class="popup-row"><span>pH</span><strong>${p.ph ?? '—'}</strong></div>
           <div class="popup-row"><span>O₂</span><strong>${p.dissolved_oxygen ?? '—'} mg/L</strong></div>`,
        )
        .addTo(map)
    })

    map.on('click', 'assets', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">${p.name}</div>
           <div class="popup-row"><span>Type</span><strong>${p.type}</strong></div>
           <div class="popup-row"><span>Sensitivity</span><strong>${((p.sensitivity ?? 0) * 100).toFixed(0)}%</strong></div>`,
        )
        .addTo(map)
    })

    map.on('click', 'sos', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new mapboxgl.Popup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">SOS: ${p.name}</div>
           <div class="popup-row"><span>ID</span><strong>${p.id}</strong></div>
           <div class="popup-row"><span>Urgency</span><strong class="${p.urgency === 'CRITICAL' ? 'alert' : ''}">${p.urgency}</strong></div>
           <div class="popup-row"><span>Status</span><strong>${p.status}</strong></div>
           <div class="popup-row"><span>Rescue via</span><strong>${(p.method || '').replace('_', ' ')}</strong></div>`,
        )
        .addTo(map)
    })

    // Cursor pointer on interactive items
    for (const layerId of ['events', 'zones-fill', 'sos', 'facilities', 'sensors', 'assets']) {
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
      pitch: 0,
      bearing: 0,
      attributionControl: true,
      antialias: true,
    })

    map.on('error', (e) => {
      console.warn('Mapbox notification:', e?.error?.message || e)
    })

    mapRef.current = map

    const geolocate = new mapboxgl.GeolocateControl({
      positionOptions: {
        enableHighAccuracy: true,
      },
      trackUserLocation: true,
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

    // Handle canvas resize automatically with ResizeObserver
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

  // ---------- Change Style on mapStyle or Token Update -----------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

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
      ['sensors', layers.sensors],
      ['events', layers.events],
      ['exposure-fill', layers.exposure],
      ['sim-line', layers.simulation],
      ['sim-points', layers.simulation],
      ['assets', layers.exposure],
      ['sos', layers.sos],
      ['zones-fill', layers.zones],
      ['zones-line', layers.zones],
      ['flood-fill', layers.flood],
      ['roads', layers.roads],
      ['buildings-3d', layers.buildings],
      ['facilities', layers.facilities],
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
      ['sensors', sensorGeo],
      ['events', eventGeo],
      ['exposure-fill', exposureGeo],
      ['assets', assetGeo],
      ['sos', sosGeo],
      ['zones-fill', zoneGeo],
      ['zones-line', zoneGeo],
      ['flood-fill', zoneGeo],
      ['roads', roadGeo],
      ['buildings-3d', buildingGeo],
      ['facilities', facilityGeo],
    ]) {
      const source = map.getSource(lid)
      if (source && typeof source.setData === 'function') {
        source.setData(geojson)
      }
    }
  }, [ready, sensorGeo, eventGeo, exposureGeo, assetGeo, sosGeo, zoneGeo, roadGeo, buildingGeo, facilityGeo])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.getSource('sim-line')?.setData(simulationGeo)
    map.getSource('sim-points')?.setData(simulationGeo)
  }, [ready, simulationGeo])

  // ---------- Fly to selected event ------------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !selectedEventId) return
    const evt = events.find((e) => e.event_id === selectedEventId)
    if (evt) {
      map.flyTo({
        center: [evt.longitude, evt.latitude],
        zoom: Math.max(map.getZoom(), 11),
        duration: 1200,
        essential: true,
      })
    }
    loadExposures()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, selectedEventId])

  // ---------- 2D / 3D camera controls ----------------------------------------
  const toggle3D = () => {
    const map = mapRef.current
    if (!map) return
    if (pitched) {
      map.easeTo({ pitch: 0, bearing: 0, duration: 800 })
      setPitched(false)
    } else {
      map.easeTo({ pitch: 58, bearing: -14, duration: 900 })
      setPitched(true)
    }
  }

  const handleRecenter = () => {
    const map = mapRef.current
    if (!map) return
    const evt = events.find((e) => e.event_id === selectedEventId)
    const targetCenter = evt ? [evt.longitude, evt.latitude] : centerCoords
    map.flyTo({ center: targetCenter, zoom: DEFAULT_ZOOM, duration: 900, essential: true })
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
          />

          {/* Collapsible Floating Legend */}
          <MapLegend />
        </>
      )}
    </div>
  )
}
