import { useEffect } from 'react'
import Header from './components/Header'
import MapView from './components/MapView'
import TacticalRail from './components/TacticalRail'
import ContextInspector from './components/ContextInspector'
import TimelineScrubber from './components/TimelineScrubber'
import OperationsDrawer from './components/OperationsDrawer'
import { useTidalis } from './store'

export default function App() {
  const init = useTidalis((s) => s.init)
  const refreshHealth = useTidalis((s) => s.refreshHealth)
  const refreshLiveData = useTidalis((s) => s.refreshLiveData)
  const loading = useTidalis((s) => s.loading)
  const leftRailCollapsed = useTidalis((s) => s.leftRailCollapsed)
  const inspectorCollapsed = useTidalis((s) => s.inspectorCollapsed)

  useEffect(() => {
    init()
    const healthTimer = setInterval(refreshHealth, 15000)
    // Synchronize live Open-Meteo & hydrodynamic telemetry periodically
    const liveTimer = setInterval(() => {
      refreshLiveData()
    }, 25000)
    return () => {
      clearInterval(healthTimer)
      clearInterval(liveTimer)
    }
  }, [init, refreshHealth, refreshLiveData])

  return (
    <div className="app">
      <Header />
      {loading ? (
        <div className="init-loading">
          <div className="init-spinner" />
          <div className="init-text">TIDALIS DIGITAL TWIN INITIALIZING…</div>
        </div>
      ) : (
        <div className="command-cockpit">
          <main
            className={`cockpit-workspace left-${
              leftRailCollapsed ? 'collapsed' : 'expanded'
            } right-${inspectorCollapsed ? 'collapsed' : 'expanded'}`}
          >
            <TacticalRail />
            <div className="center-stage">
              <MapView />
              <div className="timeline-dock">
                <TimelineScrubber />
              </div>
            </div>
            <ContextInspector />
          </main>
          <OperationsDrawer />
        </div>
      )}
    </div>
  )
}
