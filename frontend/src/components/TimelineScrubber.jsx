import { useTidalis } from '../store'

const RISK_STYLE = {
  LOW: { color: 'var(--green)', bg: 'rgba(52, 211, 153, 0.12)' },
  MODERATE: { color: 'var(--amber)', bg: 'rgba(251, 191, 36, 0.14)' },
  HIGH: { color: '#fb923c', bg: 'rgba(251, 146, 60, 0.16)' },
  CRITICAL: { color: 'var(--red)', bg: 'rgba(251, 113, 133, 0.16)' },
}

function Readout({ label, value, tone }) {
  return (
    <div className="scrub-readout">
      <span className="scrub-readout-label">{label}</span>
      <span className="scrub-readout-value" style={tone ? { color: tone } : undefined}>
        {value}
      </span>
    </div>
  )
}

export default function TimelineScrubber() {
  const meta = useTidalis((s) => s.scenarioMeta)
  const snapshot = useTidalis((s) => s.snapshot)
  const t = useTidalis((s) => s.scenarioT)
  const playing = useTidalis((s) => s.scenarioPlaying)
  const live = useTidalis((s) => s.scenarioLive)
  const seek = useTidalis((s) => s.seekScenario)
  const togglePlay = useTidalis((s) => s.toggleScenarioPlay)
  const reset = useTidalis((s) => s.resetScenario)

  if (!meta || !snapshot) {
    return (
      <div className="timeline-scrubber muted">LOADING SCENARIO TIMELINE…</div>
    )
  }

  const c = snapshot.conditions
  const risk = snapshot.aggregate_risk
  const tone = RISK_STYLE[risk] ?? RISK_STYLE.LOW
  const iso = snapshot.isolation.isolated_zones.length
  const clock = new Date(c.timestamp).toISOString().slice(11, 16)

  return (
    <div className="timeline-scrubber">
      <div className="scrub-controls">
        <button
          type="button"
          className={`scrub-btn${playing ? ' playing' : ''}`}
          onClick={togglePlay}
          title={playing ? 'Pause scenario' : 'Play scenario (WebSocket stream)'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <button type="button" className="scrub-btn ghost" onClick={reset} title="Reset to T+0">
          ⟲
        </button>
        <div className="scrub-clock">
          <span className="scrub-t">{c.label.split(' · ')[0]}</span>
          <span className="scrub-time">{clock} UTC</span>
        </div>
        <span className={`scrub-live${live ? ' on' : ''}`}>
          {live ? 'WS STREAM' : 'REST'}
        </span>
      </div>

      <div className="scrub-track">
        <input
          type="range"
          min="0"
          max={meta.duration_hours}
          step={meta.step_minutes / 60}
          value={t}
          onChange={(e) => seek(e.target.value)}
          aria-label="Scenario time scrubber"
        />
        <div className="scrub-ticks">
          {(meta.steps ?? []).map((s) => (
            <span
              key={s.t_hours}
              className={`tick${s.t_hours <= t ? ' passed' : ''}`}
              title={s.label}
            />
          ))}
        </div>
        <div className="scrub-scale">
          <span>T+0h</span>
          <span>T+1h</span>
          <span>T+2h</span>
          <span>T+3h</span>
          <span>T+4h</span>
          <span>T+5h</span>
        </div>
      </div>

      <div className="scrub-readouts">
        <div className="scrub-risk" style={{ color: tone.color, background: tone.bg }}>
          {risk}
        </div>
        <Readout label="Rain" value={`${c.rainfall_mm_h.toFixed(1)} mm/h`} tone={c.rainfall_mm_h > 30 ? 'var(--red)' : undefined} />
        <Readout label="Tide" value={`${c.tide_level_m.toFixed(2)} m`} />
        <Readout label="Surge" value={`${c.storm_surge_m.toFixed(2)} m`} />
        <Readout label="Water" value={`${c.water_level_m.toFixed(2)} m`} />
        <Readout label="Drains" value={`${Math.round(c.drainage_utilisation * 100)}%`} tone={c.drainage_utilisation > 0.85 ? 'var(--amber)' : undefined} />
        <Readout label="Blocked" value={`${snapshot.isolation.blocked_roads.length} roads`} tone={snapshot.isolation.blocked_roads.length ? 'var(--red)' : undefined} />
        <Readout label="Isolated" value={`${iso} zone${iso === 1 ? '' : 's'}`} tone={iso ? 'var(--red)' : 'var(--green)'} />
      </div>
    </div>
  )
}
