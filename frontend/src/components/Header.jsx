import { useTidalis } from '../store'

export default function Header() {
  const health = useTidalis((s) => s.health)
  const coastalState = useTidalis((s) => s.coastalState)
  const marineData = useTidalis((s) => s.marineData)
  const lastLiveUpdate = useTidalis((s) => s.lastLiveUpdate)
  const isLiveRefreshing = useTidalis((s) => s.isLiveRefreshing)
  const refreshLiveData = useTidalis((s) => s.refreshLiveData)
  const online = useTidalis((s) => s.online)

  const waveHeight = marineData?.hourly?.wave_height?.[0]
  const sst = marineData?.hourly?.sea_surface_temperature?.[0]
  const currentSpeed = marineData?.hourly?.ocean_current_velocity?.[0]

  return (
    <header className="topbar">
      <div className="brand">
        <h1>TIDALIS</h1>
        <span className="tagline">AI-Powered Coastal Digital Intelligence</span>
      </div>

      {/* Real-time Open-Meteo live ticker */}
      <div className="live-ticker">
        <span className="ticker-badge">LIVE METRICS (OPEN-METEO)</span>
        {waveHeight != null && (
          <span className="ticker-item" title="Significant Wave Height">
            🌊 <strong>{waveHeight}m</strong> waves
          </span>
        )}
        {sst != null && (
          <span className="ticker-item" title="Sea Surface Temperature">
            🌡️ <strong>{sst}°C</strong> SST
          </span>
        )}
        {currentSpeed != null && (
          <span className="ticker-item" title="Ocean Surface Current Velocity">
            🧭 <strong>{currentSpeed} km/h</strong> current
          </span>
        )}
      </div>

      <div className="spacer" />

      {/* Live sync button */}
      <button
        type="button"
        className={`refresh-live-btn${isLiveRefreshing ? ' spinning' : ''}`}
        onClick={refreshLiveData}
        title={`Sync live observations from Open-Meteo API (synced ${lastLiveUpdate || 'just now'})`}
      >
        <span className="refresh-icon">🔄</span>
        <span>{isLiveRefreshing ? 'Syncing...' : 'Sync Live'}</span>
      </button>

      <span className={`live-pill ${online ? '' : 'offline'}`}>
        <span className="dot" />
        {online ? 'API ONLINE' : 'OFFLINE'}
      </span>
      <span className={`status-pill ${coastalState.status}`}>
        {coastalState.status}
      </span>
      <span className="live-pill">
        {health.sensors ?? 0} sensors · {health.events ?? 0} events
      </span>
    </header>
  )
}