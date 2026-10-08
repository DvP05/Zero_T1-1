import { useState } from 'react'
import { useTidalis } from '../store'

const DEFAULTS = {
  current_multiplier: 1.0,
  wind_multiplier: 1.0,
  wave_multiplier: 1.0,
  duration_hours: 24,
}

export default function WhatIfPanel() {
  const runWhatIf = useTidalis((s) => s.runWhatIf)
  const simulating = useTidalis((s) => s.simulating)
  const simulation = useTidalis((s) => s.simulation)
  const [scenario, setScenario] = useState(DEFAULTS)

  const set = (key) => (e) => {
    const value = key === 'duration_hours' ? Number(e.target.value) : Number(e.target.value)
    setScenario((s) => ({ ...s, [key]: value }))
  }

  const run = async () => {
    await runWhatIf(scenario)
  }

  const pct = (v) => `${v > 0 ? '+' : ''}${Math.round((v - 1) * 100)}%`

  return (
    <div className="copilot">
      <div className="controls-row">
        <div className="control">
          <label>Current speed</label>
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.05}
            value={scenario.current_multiplier}
            onChange={set('current_multiplier')}
          />
          <span className="out">{pct(scenario.current_multiplier)}</span>
        </div>
        <div className="control">
          <label>Wind speed</label>
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.05}
            value={scenario.wind_multiplier}
            onChange={set('wind_multiplier')}
          />
          <span className="out">{pct(scenario.wind_multiplier)}</span>
        </div>
        <div className="control">
          <label>Wave height</label>
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.05}
            value={scenario.wave_multiplier}
            onChange={set('wave_multiplier')}
          />
          <span className="out">{pct(scenario.wave_multiplier)}</span>
        </div>
        <div className="control">
          <label>Duration</label>
          <select value={scenario.duration_hours} onChange={set('duration_hours')}>
            <option value={6}>6 hours</option>
            <option value={12}>12 hours</option>
            <option value={24}>24 hours</option>
          </select>
        </div>
        <button type="button" className="btn" onClick={run} disabled={simulating}>
          {simulating ? 'Running…' : 'Run Scenario'}
        </button>
      </div>

      {simulation ? (
        <div style={{ overflow: 'auto', minHeight: 0 }}>
          <table className="sim-table">
            <thead>
              <tr>
                <th>T+</th>
                <th>Latitude</th>
                <th>Longitude</th>
                <th>Radius</th>
                <th>Exposure Δ</th>
              </tr>
            </thead>
            <tbody>
              {simulation.steps.map((step) => (
                <tr key={step.hours_ahead}>
                  <td>+{step.hours_ahead}h</td>
                  <td>{step.latitude.toFixed(4)}</td>
                  <td>{step.longitude.toFixed(4)}</td>
                  <td>{step.radius_km} km</td>
                  <td className={step.exposure_change_pct >= 0 ? 'pos' : 'neg'}>
                    {step.exposure_change_pct > 0 ? '+' : ''}
                    {step.exposure_change_pct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="desc" style={{ marginTop: 10 }}>
            Scenario: current {pct(scenario.current_multiplier)}, wind {pct(scenario.wind_multiplier)},
            wave {pct(scenario.wave_multiplier)} → projected exposure change{' '}
            <b style={{ color: simulation.total_exposure_change_pct >= 0 ? 'var(--red)' : 'var(--green)' }}>
              {simulation.total_exposure_change_pct >= 0 ? '+' : ''}
              {simulation.total_exposure_change_pct.toFixed(0)}%
            </b>
            {' '}over {scenario.duration_hours}h. Projection rendered on the map.
          </div>
        </div>
      ) : (
        <div className="empty-state">
          ADJUST CONDITIONS AND RUN A WHAT-IF SCENARIO
          <br />the projected track will appear on the map
        </div>
      )}
    </div>
  )
}