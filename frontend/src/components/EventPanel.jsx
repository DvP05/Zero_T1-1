import { useTidalis } from '../store'

const EVIDENCE_CLASSES = {
  sensor: 'sensor',
  ocean: 'ocean',
  satellite: 'satellite',
  historical: 'historical',
  weather: 'weather',
}

export default function EventPanel() {
  const events = useTidalis((s) => s.events)
  const selectedEventId = useTidalis((s) => s.selectedEventId)
  const exposures = useTidalis((s) => s.exposures)

  const event = events.find((e) => e.event_id === selectedEventId)
  if (!event) {
    return (
      <div className="panel">
        <div className="panel-header"><span>Event Detail</span></div>
        <div className="panel-body">
          <div className="empty-state">SELECT AN EVENT</div>
        </div>
      </div>
    )
  }

  const conf = Math.round(event.confidence * 100)
  const highRisk = exposures.filter((e) => e.exposure_score > 0.4).length

  return (
    <div className="panel">
      <div className="panel-header">
        <span>Event · {event.event_id}</span>
        <span className={`sev ${event.severity}`}>{event.severity}</span>
      </div>
      <div className="panel-body">
        <div className="confidence-ring" style={{ '--val': conf }}>
          <div className="inner">
            {conf}%<br />
            <small>CONFIDENCE</small>
          </div>
        </div>

        <div className="metric-grid" style={{ marginTop: 12 }}>
          <div className="metric">
            <div className="label">Severity</div>
            <div className={`value ${event.severity === 'HIGH' || event.severity === 'CRITICAL' ? 'alert' : ''}`}>
              {event.severity}
            </div>
          </div>
          <div className="metric">
            <div className="label">Status</div>
            <div className="value good">{event.status}</div>
          </div>
          <div className="metric">
            <div className="label">Radius</div>
            <div className="value accent">{event.radius_km} km</div>
          </div>
          <div className="metric">
            <div className="label">Exposed Assets</div>
            <div className="value warn">{highRisk} high</div>
          </div>
          <div className="metric wide">
            <div className="label">Location</div>
            <div className="value">
              {event.latitude.toFixed(4)}, {event.longitude.toFixed(4)}
            </div>
          </div>
        </div>

        <div className="desc">{event.description}</div>

        <div className="panel-header" style={{ margin: '14px -14px -10px' }}>
          <span>Evidence</span>
        </div>
        <div className="evidence" style={{ margin: '16px 0 4px' }}>
          {event.evidence.map((ev) => (
            <div className="evidence-row" key={ev.source}>
              <span className={`src ${EVIDENCE_CLASSES[ev.source] ?? ''}`}>{ev.source}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${Math.round(ev.score * 100)}%` }}
                />
              </div>
              <span className="pct">{Math.round(ev.score * 100)}%</span>
              <span className="reason">{ev.reason}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}