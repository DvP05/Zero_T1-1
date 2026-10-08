import { useEffect, useState } from 'react'
import Header from './components/Header'
import MapView from './components/MapView'
import IncidentList from './components/IncidentList'
import LayersPanel from './components/LayersPanel'
import AlertStream from './components/AlertStream'
import TimelineScrubber from './components/TimelineScrubber'
import ZoneIntelPanel from './components/ZoneIntelPanel'
import CommandBriefPanel from './components/CommandBriefPanel'
import PriorityPanel from './components/PriorityPanel'
import EventPanel from './components/EventPanel'
import ForecastPanel from './components/ForecastPanel'
import ExposurePanel from './components/ExposurePanel'
import WhatIfPanel from './components/WhatIfPanel'
import CopilotPanel from './components/CopilotPanel'
import MitigationPanel from './components/MitigationPanel'
import TelemetryPanel from './components/TelemetryPanel'
import SOSPanel from './components/SOSPanel'
import { useTidalis } from './store'

const TABS = ['Forecast', 'Exposure', 'What-If', 'Copilot', 'Mitigation', 'SOS', 'Telemetry']

function BottomTabs() {
  const [tab, setTab] = useState('Forecast')

  return (
    <section className="bottom-tabs">
      <div className="tab-bar">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={`tab${tab === t ? ' active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="tab-body">
        {tab === 'Forecast' && <ForecastPanel />}
        {tab === 'Exposure' && <ExposurePanel />}
        {tab === 'What-If' && <WhatIfPanel />}
        {tab === 'Copilot' && <CopilotPanel />}
        {tab === 'Mitigation' && <MitigationPanel />}
        {tab === 'SOS' && <SOSPanel />}
        {tab === 'Telemetry' && <TelemetryPanel />}
      </div>
    </section>
  )
}

export default function App() {
  const init = useTidalis((s) => s.init)
  const refreshHealth = useTidalis((s) => s.refreshHealth)
  const loading = useTidalis((s) => s.loading)

  useEffect(() => {
    init()
    const timer = setInterval(refreshHealth, 15000)
    return () => clearInterval(timer)
  }, [init, refreshHealth])

  return (
    <div className="app">
      <Header />
      {loading ? (
        <div style={{ flex: 1, display: 'grid', placeItems: 'center', fontFamily: 'var(--mono)', color: 'var(--muted)', letterSpacing: 2 }}>
          TIDALIS INITIALIZING…
        </div>
      ) : (
        <>
          <main className="workspace">
            <div className="sidebar-left">
              <div className="panel">
                <div className="panel-header"><span>Incidents</span><span className="count">LIVE</span></div>
                <div className="panel-body"><IncidentList /></div>
              </div>
              <div className="panel">
                <div className="panel-body" style={{ padding: '8px 14px' }}><AlertStream /></div>
              </div>
              <LayersPanel />
            </div>
            <div className="center-col">
              <MapView />
              <TimelineScrubber />
            </div>
            <div className="sidebar-right">
              <ZoneIntelPanel />
              <div className="panel">
                <div className="panel-header"><span>Command Brief</span><span className="count">GenAI</span></div>
                <div className="panel-body"><CommandBriefPanel /></div>
              </div>
              <div className="panel">
                <div className="panel-body"><PriorityPanel /></div>
              </div>
              <EventPanel />
            </div>
          </main>
          <BottomTabs />
        </>
      )}
    </div>
  )
}
