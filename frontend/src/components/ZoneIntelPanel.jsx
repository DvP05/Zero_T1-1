import { useTidalis } from '../store'

export default function ZoneIntelPanel() {
  const snapshot = useTidalis((s) => s.snapshot)
  const selectedZoneId = useTidalis((s) => s.selectedZoneId)
  const selectZone = useTidalis((s) => s.selectZone)

  if (!snapshot) return <div className="empty-state">LOADING ZONE INTELLIGENCE…</div>

  const zone =
    snapshot.zones.find((z) => z.zone_id === selectedZoneId) ??
    snapshot.zones.find((z) => z.zone_id === snapshot.priorities.top_zone) ??
    snapshot.zones[0]

  const priority =
    snapshot.priorities.items.find((p) => p.zone_id === zone.zone_id) ?? null
  const pct = Math.round(zone.flood_probability * 100)

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

        {zone.facilities_threatened.length > 0 && (
          <div className="zone-facilities">
            <div className="label" style={{ marginBottom: 6 }}>Facilities threatened</div>
            <div className="chip-grid">
              {zone.facilities_threatened.map((f) => (
                <span key={f} className="chip" style={{ cursor: 'default', borderColor: 'rgba(251,113,133,0.45)', color: 'var(--red)' }}>
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}

        {priority && (
          <div className="zone-priority-line">
            Priority #{priority.rank} · score {priority.priority_score.toFixed(2)} ·{' '}
            <span style={{ color: priority.isolated ? 'var(--red)' : 'var(--accent)' }}>
              {priority.urgency}
            </span>
            {priority.isolated && ' · ISOLATED'}
          </div>
        )}

        <div className="evidence" style={{ marginTop: 10 }}>
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
