import { useTidalis } from '../store'

export default function CommandBriefPanel() {
  const snapshot = useTidalis((s) => s.snapshot)

  if (!snapshot) {
    return <div className="empty-state">GENERATING COMMAND BRIEF…</div>
  }

  const top = snapshot.priorities.items[0]
  const zone = snapshot.zones.find((z) => z.zone_id === (top?.zone_id ?? snapshot.priorities.top_zone))
  const drivers = (zone?.drivers ?? []).slice(0, 4)

  return (
    <div className="brief-panel">
      <div className="brief-headline">{snapshot.brief_headline}</div>
      <p className="brief-body">{snapshot.brief}</p>

      {drivers.length > 0 && (
        <div className="brief-drivers">
          <div className="label" style={{ marginBottom: 6 }}>
            Why — model drivers ({zone.zone_id})
          </div>
          {drivers.map((d) => (
            <div key={d.feature} className="driver-row">
              <span className="driver-name">{d.label}</span>
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
              <span className="driver-pct">
                {d.contribution >= 0 ? '+' : ''}
                {(d.contribution * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="brief-footer">
        TIDALIS COPILOT · grounded in model output · DEMO DATA
      </div>
    </div>
  )
}
