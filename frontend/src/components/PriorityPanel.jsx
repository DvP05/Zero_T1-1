import { useTidalis } from '../store'

const URGENCY_COLOR = {
  IMMEDIATE: 'var(--red)',
  URGENT: '#fb923c',
  ELEVATED: 'var(--amber)',
  MONITOR: 'var(--muted)',
}

export default function PriorityPanel() {
  const snapshot = useTidalis((s) => s.snapshot)
  const selectedZoneId = useTidalis((s) => s.selectedZoneId)
  const selectZone = useTidalis((s) => s.selectZone)

  if (!snapshot) return <div className="empty-state">COMPUTING PRIORITY BOARD…</div>

  const { items, formula, generated_note } = snapshot.priorities

  return (
    <div className="priority-panel">
      <div className="priority-head">
        <div>
          <div className="priority-title">Emergency Response Priority</div>
          <div className="priority-formula">{formula}</div>
        </div>
        <span className="priority-count">{items.length}</span>
      </div>

      <div className="priority-list">
        {items.map((item) => {
          const color = URGENCY_COLOR[item.urgency] ?? 'var(--muted)'
          const selected = item.zone_id === selectedZoneId
          return (
            <button
              type="button"
              key={item.zone_id}
              className={`priority-item${selected ? ' selected' : ''}${item.isolated ? ' isolated' : ''}`}
              onClick={() => selectZone(item.zone_id)}
            >
              <div className="priority-rank" style={{ color }}>
                #{item.rank}
              </div>
              <div className="priority-main">
                <div className="priority-zone">
                  <span>{item.zone_name}</span>
                  <span className="priority-urgency" style={{ color }}>
                    {item.urgency}
                  </span>
                </div>
                <div className="priority-scorebar">
                  <div
                    className="priority-scorefill"
                    style={{
                      width: `${item.priority_score * 100}%`,
                      background: `linear-gradient(90deg, #0ea5e9, ${color})`,
                    }}
                  />
                </div>
                <div className="priority-meta">
                  <span>P {Math.round(item.flood_probability * 100)}%</span>
                  <span>depth {item.flood_depth_m.toFixed(2)} m</span>
                  <span>assets {item.affected_facility_count}/{item.total_facility_count}</span>
                  <span>{(item.population / 1000).toFixed(1)}k ppl</span>
                  {item.onset_hours != null && <span>onset +{item.onset_hours.toFixed(1)}h</span>}
                </div>
                <div className="priority-reasons">
                  {item.isolated && <span className="iso-flag">ISOLATED ENCLAVE</span>}
                  {item.reasons.slice(0, 2).map((r) => (
                    <span key={r} className="priority-reason">{r}</span>
                  ))}
                </div>
              </div>
              <div className="priority-score" style={{ color }}>
                {item.priority_score.toFixed(2)}
              </div>
            </button>
          )
        })}
      </div>

      <div className="priority-note">{generated_note}</div>
    </div>
  )
}
