import { useState } from 'react'
import { useTidalis } from '../store'
import IncidentList from './IncidentList'
import AlertStream from './AlertStream'
import LayersPanel from './LayersPanel'
import LiveMarineFeed from './LiveMarineFeed'

export default function TacticalRail() {
  const leftRailCollapsed = useTidalis((s) => s.leftRailCollapsed)
  const toggleLeftRail = useTidalis((s) => s.toggleLeftRail)
  const setLeftRailCollapsed = useTidalis((s) => s.setLeftRailCollapsed)
  const events = useTidalis((s) => s.events)
  const snapshot = useTidalis((s) => s.snapshot)

  const [activeTab, setActiveTab] = useState('incidents') // 'incidents' | 'layers'

  const activeAlertsCount = snapshot?.alerts?.length ?? 0
  const eventCount = events?.length ?? 0

  if (leftRailCollapsed) {
    return (
      <aside className="tactical-rail collapsed">
        <button
          type="button"
          className="rail-icon-btn expand-toggle"
          onClick={toggleLeftRail}
          title="Expand Tactical Rail (Incidents & Layers)"
        >
          ▶
        </button>

        <div className="rail-icons">
          <button
            type="button"
            className={`rail-icon-btn${activeTab === 'incidents' ? ' active' : ''}`}
            onClick={() => {
              setActiveTab('incidents')
              setLeftRailCollapsed(false)
            }}
            title={`Incidents (${eventCount})`}
          >
            <span className="icon">🚨</span>
            <span className="badge">{eventCount}</span>
          </button>

          <button
            type="button"
            className={`rail-icon-btn${activeAlertsCount > 0 ? ' warn' : ''}`}
            onClick={() => {
              setActiveTab('incidents')
              setLeftRailCollapsed(false)
            }}
            title={`Live Alerts (${activeAlertsCount})`}
          >
            <span className="icon">⚡</span>
            {activeAlertsCount > 0 && <span className="badge alert">{activeAlertsCount}</span>}
          </button>

          <button
            type="button"
            className={`rail-icon-btn${activeTab === 'layers' ? ' active' : ''}`}
            onClick={() => {
              setActiveTab('layers')
              setLeftRailCollapsed(false)
            }}
            title="Layer Filters"
          >
            <span className="icon">🗂️</span>
          </button>
        </div>
      </aside>
    )
  }

  return (
    <aside className="tactical-rail expanded panel">
      <div className="panel-header rail-header">
        <div className="tab-pill-group">
          <button
            type="button"
            className={`tab-pill${activeTab === 'incidents' ? ' active' : ''}`}
            onClick={() => setActiveTab('incidents')}
          >
            Incidents & Alerts
            <span className="mini-badge">{eventCount}</span>
          </button>
          <button
            type="button"
            className={`tab-pill${activeTab === 'layers' ? ' active' : ''}`}
            onClick={() => setActiveTab('layers')}
          >
            Layers
          </button>
        </div>

        <button
          type="button"
          className="collapse-btn"
          onClick={toggleLeftRail}
          title="Collapse Sidebar"
        >
          ◀
        </button>
      </div>

      <div className="panel-body rail-body">
        {activeTab === 'incidents' ? (
          <div className="rail-feed">
            {/* Real-time Marine Telemetry */}
            <div className="feed-section">
              <LiveMarineFeed />
            </div>

            {/* Live Alerts Section */}
            <div className="feed-section">
              <AlertStream />
            </div>

            {/* Incidents Section */}
            <div className="feed-section">
              <div className="section-title">
                <span>Active Incidents</span>
                <span className="count">LIVE</span>
              </div>
              <div className="feed-list">
                <IncidentList />
              </div>
            </div>
          </div>
        ) : (
          <div className="rail-layers">
            <LayersPanel />
          </div>
        )}
      </div>
    </aside>
  )
}
