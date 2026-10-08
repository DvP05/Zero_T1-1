import { useTidalis } from '../store'

export default function IncidentList() {
  const events = useTidalis((s) => s.events)
  const selectedEventId = useTidalis((s) => s.selectedEventId)
  const selectEvent = useTidalis((s) => s.selectEvent)

  if (events.length === 0) {
    return <div className="empty-state">NO ACTIVE EVENTS</div>
  }

  return events.map((evt) => (
    <button
      key={evt.event_id}
      type="button"
      className={`incident-item${evt.event_id === selectedEventId ? ' selected' : ''}`}
      onClick={() => selectEvent(evt.event_id)}
    >
      <div className="row">
        <span className="event-id">EVT {evt.event_id.replace('evt-', '')}</span>
        <span className={`sev ${evt.severity}`}>{evt.severity}</span>
      </div>
      <div className="meta">
        <span>{evt.event_type.replace(/_/g, ' ')}</span>
        <span>{(evt.confidence * 100).toFixed(0)}%</span>
      </div>
    </button>
  ))
}