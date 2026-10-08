import { useEffect, useMemo, useRef, useState } from 'react'
import { Map as MlMap, Popup as MlPopup } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useTidalis } from '../store'

const CENTER = [80.0, 18.0]
const BASE_STYLE = "https://demotiles.maplibre.org/style.json"

const RISK_MATCH = [
  'match',
  ['get', 'risk_level'],
  'CRITICAL', '#fb7185',
  'HIGH', '#fb923c',
  'MODERATE', '#fbbf24',
  '#34d399',
]

// Approximate geodesic circle as a polygon (radius in km)
function circlePolygon(lon, lat, radiusKm, points = 36) {
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

export default function MapView() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const rafRef = useRef(0)
  const [ready, setReady] = useState(false)
  const [pitched, setPitched] = useState(false)

  const events = useTidalis((s) => s.events)
  const sensors = useTidalis((s) => s.sensors)
  const readings = useTidalis((s) => s.readings)
  const assets = useTidalis((s) => s.assets)
  const selectedEventId = useTidalis((s) => s.selectedEventId)
  const layers = useTidalis((s) => s.layers)
  const simulation = useTidalis((s) => s.simulation)
  const selectEvent = useTidalis((s) => s.selectEvent)
  const loadExposures = useTidalis((s) => s.loadExposures)

  // --- scenario / digital-twin state ---
  const geo = useTidalis((s) => s.geo)
  const snapshot = useTidalis((s) => s.snapshot)
  const selectZone = useTidalis((s) => s.selectZone)
  const selectedZoneId = useTidalis((s) => s.selectedZoneId)

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

  // --- digital twin layers ------------------------------------------------
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

  // ---------- init map ------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new MlMap({
      container: containerRef.current,
      style: BASE_STYLE,
      center: CENTER,
      zoom: 4.0,
      pitch: 0,
      attributionControl: true,
    })
    mapRef.current = map

    map.on('load', () => {
      const pulse = new ImageData(new Uint8ClampedArray(128 * 128 * 4), 128, 128)
      map.addImage('pulse-dot', pulse)

      const empty = { type: 'FeatureCollection', features: [] }

      // layer order: exposure → zones → flood → roads → buildings(3D) → assets → sensors → events
      map.addLayer({
        id: 'exposure-fill',
        type: 'fill',
        source: { type: 'geojson', data: empty },
        paint: {
          'fill-color': '#fbbf24',
          'fill-opacity': 0.10,
          'fill-outline-color': 'rgba(251,191,36,0.55)',
        },
      })
      map.addLayer({
        id: 'zones-fill',
        type: 'fill',
        source: { type: 'geojson', data: empty },
        paint: {
          'fill-color': ['case', ['get', 'selected'], '#22d3ee', RISK_MATCH],
          'fill-opacity': [
            '+', 0.10,
            ['*', ['min', ['get', 'flood_depth_m'], 2.5], 0.18],
          ],
        },
      })
      map.addLayer({
        id: 'flood-fill',
        type: 'fill',
        source: { type: 'geojson', data: empty },
        paint: {
          'fill-color': '#0ea5e9',
          'fill-opacity': [
            'case',
            ['>', ['get', 'flood_depth_m'], 0.02],
            ['*', ['min', ['get', 'flood_depth_m'], 2.5], 0.30],
            0,
          ],
          'fill-outline-color': 'rgba(34,211,238,0.6)',
        },
      })
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
          'line-width': ['case', ['get', 'selected'], 3, 1.6],
          'line-dasharray': ['case', ['get', 'isolated'], ['literal', [2, 1.2]], ['literal', [1, 0]]],
        },
      })
      map.addLayer({
        id: 'roads',
        type: 'line',
        source: { type: 'geojson', data: empty },
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['case', ['get', 'passable'], '#4b628a', '#fb7185'],
          'line-width': [
            'case',
            ['get', 'passable'], ['case', ['get', 'critical'], 3.2, 2.0],
            ['case', ['get', 'critical'], 4.4, 3.0],
          ],
          'line-opacity': 0.95,
          'line-blur': 0.4,
        },
      })
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
          'fill-extrusion-opacity': 0.72,
        },
      })
      map.addLayer({
        id: 'sim-line',
        type: 'line',
        source: { type: 'geojson', data: empty },
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#a78bfa', 'line-width': 2.5, 'line-dasharray': [2, 1.5] },
      })
      map.addLayer({
        id: 'sim-points',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': 5,
          'circle-color': '#a78bfa',
          'circle-stroke-color': '#eaf2ff',
          'circle-stroke-width': 1,
        },
      })
      map.addLayer({
        id: 'assets',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': 4,
          'circle-color': '#5f7194',
          'circle-opacity': 0.65,
        },
      })
      map.addLayer({
        id: 'facilities',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': ['case', ['get', 'threatened'], 8, 6],
          'circle-color': ['case', ['get', 'threatened'], '#fb7185', '#22d3ee'],
          'circle-stroke-color': '#eaf2ff',
          'circle-stroke-width': 1.4,
        },
      })
      map.addLayer({
        id: 'sensors',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': ['case', ['get', 'anomalous'], 9, 6],
          'circle-color': ['case', ['get', 'anomalous'], '#fb7185', '#22d3ee'],
          'circle-stroke-color': '#eaf2ff',
          'circle-stroke-width': 1.2,
        },
      })
      map.addLayer({
        id: 'sos',
        type: 'circle',
        source: { type: 'geojson', data: empty },
        paint: {
          'circle-radius': 10,
          'circle-color': ['case', ['==', ['get', 'status'], 'RESCUED'], '#34d399', '#ffffff'],
          'circle-stroke-color': '#eaf2ff',
          'circle-stroke-width': 2,
        },
      })
      map.addLayer({
        id: 'events',
        type: 'symbol',
        source: { type: 'geojson', data: empty },
        layout: {
          'icon-image': 'pulse-dot',
          'icon-size': 0.2,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      })

      setReady(true)
    })

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
      new MlPopup({ closeButton: true, offset: 18 })
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
      new MlPopup({ closeButton: true, offset: 18 })
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
      new MlPopup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">${p.name}</div>
           <div class="popup-row"><span>Type</span><strong>${p.type}</strong></div>
           <div class="popup-row"><span>Sensitivity</span><strong>${(p.sensitivity * 100).toFixed(0)}%</strong></div>`,
        )
        .addTo(map)
    })

    map.on('click', 'sos', (e) => {
      const p = e.features[0]?.properties
      if (!p) return
      new MlPopup({ closeButton: true, offset: 18 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div class="popup-title">SOS: ${p.name}</div>
           <div class="popup-row"><span>ID</span><strong>${p.id}</strong></div>
           <div class="popup-row"><span>Urgency</span><strong class="${p.urgency === 'CRITICAL' ? 'alert' : ''}">${p.urgency}</strong></div>
           <div class="popup-row"><span>Status</span><strong>${p.status}</strong></div>
           <div class="popup-row"><span>Rescue via</span><strong>${p.method.replace('_', ' ')}</strong></div>`,
        )
        .addTo(map)
    })

    for (const layerId of ['events', 'zones-fill', 'sos', 'facilities']) {
      map.on('mouseenter', layerId, () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', layerId, () => { map.getCanvas().style.cursor = '' })
    }

    // ---- pulsing animation ------------------------------------------------
    const SIZE = 128
    let phase = 0
    const animate = () => {
      const map2 = mapRef.current
      if (!map2) return
      try {
        const data = new Uint8ClampedArray(SIZE * SIZE * 4)
        const radius = SIZE / 2 * (0.28 + 0.16 * Math.sin((phase += 0.06)))
        const core = radius * 0.55
        for (let i = 0; i < data.length; i += 4) {
          const x = (i / 4) % SIZE
          const y = Math.floor(i / 4 / SIZE)
          const d = Math.hypot(x - SIZE / 2, y - SIZE / 2)
          if (d < core) {
            data[i] = 251; data[i + 1] = 113; data[i + 2] = 133; data[i + 3] = 235
          } else if (d < radius) {
            const alpha = Math.round(110 * (1 - (d - core) / (radius - core)))
            data[i] = 251; data[i + 1] = 113; data[i + 2] = 133; data[i + 3] = alpha
          }
        }
        map2.updateImage('pulse-dot', new ImageData(data, SIZE, SIZE))
      } catch { /* map disposed */ }
      rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(rafRef.current)
      map.remove()
      mapRef.current = null
    }
  }, [selectEvent, selectZone])

  // ---------- layer visibility ----------------------------------------------
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
      if (map.getLayer(lid)) map.setLayoutProperty(lid, 'visibility', isOn ? 'visible' : 'none')
    }
  }, [layers, ready])

  // ---------- data updates ---------------------------------------------------
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
      if (source) source.setData(geojson)
    }
  }, [ready, sensorGeo, eventGeo, exposureGeo, assetGeo, sosGeo, zoneGeo, roadGeo, buildingGeo, facilityGeo])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.getSource('sim-line')?.setData(simulationGeo)
    map.getSource('sim-points')?.setData(simulationGeo)
  }, [ready, simulationGeo])

  // ---------- fly to selected event -----------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !selectedEventId) return
    const evt = events.find((e) => e.event_id === selectedEventId)
    if (evt) map.flyTo({ center: [evt.longitude, evt.latitude], zoom: Math.max(map.getZoom(), 10.2), duration: 1200 })
    // refresh exposures when the selected event changes
    loadExposures()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, selectedEventId])

  // ---------- 3D digital-twin toggle ----------------------------------------
  const toggle3D = () => {
    const map = mapRef.current
    if (!map) return
    if (pitched) {
      map.easeTo({ pitch: 0, bearing: 0, duration: 700 })
      setPitched(false)
    } else {
      map.easeTo({ pitch: 58, bearing: -12, duration: 900 })
      setPitched(true)
    }
  }

  const selectedEvent = events.find((e) => e.event_id === selectedEventId)
  const showSim = layers.simulation && simulation?.steps?.length > 0
  const isoZones = snapshot?.isolation?.isolated_zones ?? []

  return (
    <div className="map-pane panel">
      <div className="panel-header">
        <span>3D Digital Twin · Coastal Operations Map</span>
        <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="count">
            {snapshot ? `T+${snapshot.t_hours.toFixed(2)}h · ${snapshot.aggregate_risk}` : 'Goa · 15.30 N, 73.97 E'}
          </span>
          <button
            type="button"
            className={`copy-btn${pitched ? ' active' : ''}`}
            style={{ borderColor: pitched ? 'var(--accent)' : 'var(--border)', color: pitched ? 'var(--accent)' : 'var(--muted)' }}
            onClick={toggle3D}
          >
            {pitched ? '2D' : '3D'}
          </button>
        </span>
      </div>
      <div className="panel-body">
        <div className="map-wrap" ref={containerRef} />
        <div className="map-hint">Click a zone to inspect its intelligence</div>
        <div className="map-legend">
          <div className="li"><span className="sw" style={{ background: '#34d399' }} /> Zone · LOW</div>
          <div className="li"><span className="sw" style={{ background: '#fbbf24' }} /> Zone · MODERATE</div>
          <div className="li"><span className="sw" style={{ background: '#fb923c' }} /> Zone · HIGH</div>
          <div className="li"><span className="sw" style={{ background: '#fb7185' }} /> Zone · CRITICAL</div>
          <div className="li"><span className="sw" style={{ background: '#0ea5e9' }} /> Rising flood water</div>
          <div className="li"><span className="sw" style={{ background: '#fb7185' }} /> Impassable road</div>
          <div className="li"><span className="sw" style={{ background: '#22d3ee' }} /> Critical facility</div>
          {isoZones.length > 0 && (
            <div className="li" style={{ color: 'var(--red)' }}>
              ⚠ Isolated: {isoZones.join(', ')}
            </div>
          )}
          {showSim && (
            <div className="li"><span className="sw" style={{ background: '#a78bfa' }} /> What-If projection</div>
          )}
          {selectedEvent ? (
            <div className="li" style={{ color: 'var(--text)' }}>
              EVT {selectedEvent.event_id} · {(selectedEvent.confidence * 100).toFixed(0)}% conf
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
