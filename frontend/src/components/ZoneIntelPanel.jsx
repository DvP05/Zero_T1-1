import { useMemo } from 'react'
import { useTidalis } from '../store'

export default function ZoneIntelPanel() {
  const snapshot = useTidalis((s) => s.snapshot)
  const selectedZoneId = useTidalis((s) => s.selectedZoneId)
  const selectZone = useTidalis((s) => s.selectZone)
  const geo = useTidalis((s) => s.geo)
  const flyToTarget = useTidalis((s) => s.flyToTarget)

  if (!snapshot) return <div className="empty-state">LOADING ZONE INTELLIGENCE…</div>

  const zone =
    snapshot.zones.find((z) => z.zone_id === selectedZoneId) ??
    snapshot.zones.find((z) => z.zone_id === snapshot.priorities.top_zone) ??
    snapshot.zones[0]

  const priority =
    snapshot.priorities.items.find((p) => p.zone_id === zone.zone_id) ?? null
  const pct = Math.round(zone.flood_probability * 100)

  // Blocked and affected roads
  const blockedRoads = snapshot.isolation?.blocked_roads ?? []
  const passableRoads = snapshot.isolation?.passable_roads ?? []

  // Extract threatened facilities & buildings in this zone
  const threatenedFacilities = zone.facilities_threatened || []
  const allFacilities = useMemo(() => {
    return (geo?.layers?.facilities?.features || []).filter(
      (f) => f.properties?.zone_id === zone.zone_id || threatenedFacilities.includes(f.properties?.name)
    )
  }, [geo, zone.zone_id, threatenedFacilities])

  const zoneBuildings = useMemo(() => {
    return (geo?.layers?.buildings?.features || []).filter(
      (b) => b.properties?.zone_id === zone.zone_id
    )
  }, [geo, zone.zone_id])

  const buildingsAtRiskCount = Math.round(
    zoneBuildings.length > 0
      ? zoneBuildings.length * (zone.flood_probability > 0.4 ? zone.flood_probability : 0.2)
      : Math.round(zone.population * 0.04 * (zone.flood_depth_m > 0.1 ? 1 : 0.2))
  )

  const handleFlyTo = (coords) => {
    if (coords && coords.length >= 2) {
      flyToTarget({
        lng: coords[0],
        lat: coords[1],
        zoom: 16.2,
        pitch: 52,
        bearing: -12,
      })
    }
  }

  return (
    <div className="panel zone-intel">
      <div className="panel-header">
        <span>Zone Intelligence</span>
        <span className="zone-picker">
          <select
            value={zone.zone_id}
            onChange={(e) => selectZone(e.target.value)}
            aria-label="Select zone"
          >
            {snapshot.zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.zone_id} · {z.risk_level}
              </option>
            ))}
          </select>
        </span>
      </div>
      <div className="panel-body">
        <div className="zone-title-row">
          <div>
            <div className="zone-name">{zone.zone_name}</div>
            <div className="zone-sub">
              elev {zone.elevation_m.toFixed(1)} m · pop {zone.population.toLocaleString()} ·
              vulnerability {(zone.vulnerability * 100).toFixed(0)}%
            </div>
          </div>
          <span
            className="risk-badge"
            style={{ color: zone.risk_color, borderColor: zone.risk_color }}
          >
            {zone.risk_level}
          </span>
        </div>

        <div className="zone-prob-row">
          <div className="confidence-ring" style={{ '--val': pct }}>
            <div className="inner">
              {pct}%<br />
              <small>FLOOD PROB</small>
            </div>
          </div>
          <div className="metric-grid" style={{ flex: 1 }}>
            <div className="metric">
              <div className="label">Depth</div>
              <div className={`value ${zone.flood_depth_m > 0.5 ? 'alert' : ''}`}>
                {zone.flood_depth_m.toFixed(2)}<small> m</small>
              </div>
            </div>
            <div className="metric">
              <div className="label">Interval</div>
              <div className="value accent" style={{ fontSize: 14 }}>
                {Math.round(zone.interval_low * 100)}–{Math.round(zone.interval_high * 100)}%
              </div>
            </div>
            <div className="metric">
              <div className="label">Onset</div>
              <div className="value warn" style={{ fontSize: 14 }}>
                {zone.onset_hours != null ? `+${zone.onset_hours.toFixed(1)} h` : '—'}
              </div>
            </div>
            <div className="metric">
              <div className="label">Peak</div>
              <div className="value" style={{ fontSize: 14 }}>
                {zone.peak_hours != null ? `+${zone.peak_hours.toFixed(1)} h` : '—'}
                <small> {(zone.peak_probability * 100).toFixed(0)}%</small>
              </div>
            </div>
          </div>
        </div>

        {/* 1. Affected Critical Facilities */}
        {threatenedFacilities.length > 0 && (
          <div className="zone-facilities" style={{ marginTop: 10 }}>
            <div className="label" style={{ marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
              <span>Threatened Critical Facilities</span>
              <span style={{ color: 'var(--red)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                {threatenedFacilities.length} at risk
              </span>
            </div>
            <div className="chip-grid">
              {threatenedFacilities.map((f) => (
                <span
                  key={f}
                  className="chip"
                  style={{
                    cursor: 'pointer',
                    borderColor: 'rgba(251,113,133,0.5)',
                    color: 'var(--red)',
                    background: 'var(--red-dim)',
                  }}
                  title="Click to view facility"
                  onClick={() => {
                    const match = allFacilities.find((fac) => fac.properties?.name === f)
                    if (match?.geometry?.coordinates) handleFlyTo(match.geometry.coordinates)
                  }}
                >
                  ⚠️ {f}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 2. Affected Roads & Access Chokepoints */}
        <div className="zone-roads" style={{ marginTop: 12 }}>
          <div className="label" style={{ marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
            <span>Affected Roads & Corridors</span>
            <span style={{ color: blockedRoads.length > 0 ? 'var(--amber)' : 'var(--green)', fontFamily: 'var(--mono)', fontSize: 10 }}>
              {blockedRoads.length} Cut-Edges
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 110, overflowY: 'auto' }}>
            {blockedRoads.slice(0, 3).map((r) => (
              <div
                key={r.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: 11,
                  background: 'var(--panel-2)',
                  padding: '5px 8px',
                  borderRadius: 4,
                  borderLeft: '3px solid var(--red)',
                }}
              >
                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%', color: 'var(--text-hi)' }}>
                  🚫 {r.name}
                </div>
                <span style={{ color: 'var(--red)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                  +{r.submersion_m.toFixed(2)}m
                </span>
              </div>
            ))}
            {passableRoads.slice(0, 2).map((r) => (
              <div
                key={r.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: 11,
                  background: 'var(--panel-2)',
                  padding: '5px 8px',
                  borderRadius: 4,
                  borderLeft: '3px solid var(--green)',
                }}
              >
                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%', color: 'var(--text)' }}>
                  ✓ {r.name}
                </div>
                <span style={{ color: 'var(--green)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                  Passable
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 3. Buildings & Structural Impact */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--panel-2)', padding: '6px 10px', borderRadius: 6, marginTop: 10 }}>
          <span style={{ fontSize: 11, color: 'var(--text)' }}>Buildings in Inundation Contour:</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 'bold', color: zone.flood_depth_m > 0.2 ? 'var(--red)' : 'var(--text-hi)' }}>
            ~{buildingsAtRiskCount} structures
          </span>
        </div>

        {priority && (
          <div className="zone-priority-line" style={{ marginTop: 10 }}>
            Priority #{priority.rank} · score {priority.priority_score.toFixed(2)} ·{' '}
            <span style={{ color: priority.isolated ? 'var(--red)' : 'var(--accent)' }}>
              {priority.urgency}
            </span>
            {priority.isolated && ' · ISOLATED'}
          </div>
        )}

        {/* 4. Explainable Drivers */}
        <div className="evidence" style={{ marginTop: 10 }}>
          <div className="label" style={{ marginBottom: 6 }}>Model Drivers (SHAP Attribution)</div>
          {zone.drivers.map((d) => (
            <div className="evidence-row" key={d.feature}>
              <span className="src weather">{d.feature.split('_')[0]}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{
                    width: `${Math.min(100, Math.abs(d.contribution) * 260)}%`,
                    background:
                      d.contribution >= 0
                        ? 'linear-gradient(90deg, #f59e0b, var(--red))'
                        : 'linear-gradient(90deg, #0ea5e9, var(--green))',
                  }}
                />
              </div>
              <span className="pct">
                {d.contribution >= 0 ? '+' : ''}
                {(d.contribution * 100).toFixed(0)}%
              </span>
              <span className="reason">{d.reason}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
