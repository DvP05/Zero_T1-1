import { useTidalis } from '../store'

const LEVEL_COLOR = {
  CRITICAL: 'var(--red)',
  WARNING: 'var(--amber)',
  WATCH: 'var(--accent)',
  INFO: 'var(--muted)',
}

export default function AlertStream() {
  const snapshot = useTidalis((s) => s.snapshot)
  const playing = useTidalis((s) => s.scenarioPlaying)

  const alerts = snapshot?.alerts ?? []

  return (
    <div className="alert-stream">
      <div className="alert-head">
        <span>Live Alerts</span>
        <span className={`alert-pulse${playing ? ' on' : ''}`}>{playing ? 'STREAMING' : 'STANDBY'}</span>
      </div>
      {alerts.length === 0 ? (
        <div className="empty-state" style={{ padding: '14px 0' }}>
          NO ACTIVE ALERTS
        </div>
      ) : (
        <div className="alert-list">
          {alerts.map((a) => {
            const color = LEVEL_COLOR[a.level] ?? 'var(--muted)'
            return (
              <div key={a.id} className="alert-item" style={{ borderLeftColor: color }}>
                <div className="alert-level" style={{ color }}>{a.level}</div>
                <div className="alert-message">{a.message}</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
