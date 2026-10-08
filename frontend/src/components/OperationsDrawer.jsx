import { useTidalis } from '../store'
import ForecastPanel from './ForecastPanel'
import ExposurePanel from './ExposurePanel'
import WhatIfPanel from './WhatIfPanel'
import CopilotPanel from './CopilotPanel'
import MitigationPanel from './MitigationPanel'
import SOSPanel from './SOSPanel'
import TelemetryPanel from './TelemetryPanel'

const TABS = [
  { id: 'Copilot', label: 'Copilot', icon: '🤖' },
  { id: 'What-If', label: 'What-If Simulator', icon: '🔮' },
  { id: 'Mitigation', label: 'Mitigation Actions', icon: '🛡️' },
  { id: 'SOS', label: 'SOS Triage', icon: '🆘' },
  { id: 'Forecast', label: 'Forecast Charts', icon: '📊' },
  { id: 'Exposure', label: 'Asset Exposure', icon: '🎯' },
  { id: 'Telemetry', label: 'ML Telemetry', icon: '📉' },
]

export default function OperationsDrawer() {
  const open = useTidalis((s) => s.operationsOpen)
  const toggleOperations = useTidalis((s) => s.toggleOperations)
  const tab = useTidalis((s) => s.operationsTab)
  const setOperationsTab = useTidalis((s) => s.setOperationsTab)
  const sosTickets = useTidalis((s) => s.sosTickets)

  const pendingSos = (sosTickets || []).filter((t) => t.status !== 'RESCUED').length

  if (!open) {
    return (
      <footer className="operations-drawer closed">
        <div className="drawer-bar-collapsed">
          <button
            type="button"
            className="drawer-toggle-btn"
            onClick={toggleOperations}
            title="Expand Operations Console"
          >
            <span className="icon">▲</span>
            <span className="label">Operations Console</span>
          </button>

          <div className="drawer-summary-chips">
            <button
              type="button"
              className="chip-btn"
              onClick={() => setOperationsTab('Copilot')}
            >
              🤖 Copilot Ready
            </button>
            <button
              type="button"
              className={`chip-btn${pendingSos > 0 ? ' alert' : ''}`}
              onClick={() => setOperationsTab('SOS')}
            >
              🆘 {pendingSos} Active SOS
            </button>
            <button
              type="button"
              className="chip-btn"
              onClick={() => setOperationsTab('What-If')}
            >
              🔮 What-If Simulator
            </button>
            <button
              type="button"
              className="chip-btn"
              onClick={() => setOperationsTab('Forecast')}
            >
              📊 Surge Forecast
            </button>
          </div>

          <button
            type="button"
            className="drawer-open-pill"
            onClick={toggleOperations}
          >
            Open Console ▴
          </button>
        </div>
      </footer>
    )
  }

  return (
    <footer className="operations-drawer opened panel">
      <div className="panel-header drawer-header">
        <div className="drawer-tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`drawer-tab${tab === t.id ? ' active' : ''}`}
              onClick={() => setOperationsTab(t.id)}
            >
              <span className="tab-icon">{t.icon}</span>
              <span className="tab-text">{t.label}</span>
              {t.id === 'SOS' && pendingSos > 0 && (
                <span className="tab-badge">{pendingSos}</span>
              )}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="drawer-minimize-btn"
          onClick={toggleOperations}
          title="Minimize Operations Console"
        >
          ▼ Minimize
        </button>
      </div>

      <div className="panel-body drawer-body">
        {tab === 'Copilot' && <CopilotPanel />}
        {tab === 'What-If' && <WhatIfPanel />}
        {tab === 'Mitigation' && <MitigationPanel />}
        {tab === 'SOS' && <SOSPanel />}
        {tab === 'Forecast' && <ForecastPanel />}
        {tab === 'Exposure' && <ExposurePanel />}
        {tab === 'Telemetry' && <TelemetryPanel />}
      </div>
    </footer>
  )
}
