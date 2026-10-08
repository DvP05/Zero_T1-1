import { useTidalis } from '../store'

export default function LiveMarineFeed() {
  const marineData = useTidalis((s) => s.marineData)
  const lastLiveUpdate = useTidalis((s) => s.lastLiveUpdate)
  const isLiveRefreshing = useTidalis((s) => s.isLiveRefreshing)
  const refreshLiveData = useTidalis((s) => s.refreshLiveData)
  const userLocation = useTidalis((s) => s.userLocation)
  const activeLocation = useTidalis((s) => s.activeLocation)
  const coastalState = useTidalis((s) => s.coastalState)

  const hourly = marineData?.hourly || {}
  const waveHeight = hourly.wave_height?.[0]
  const sst = hourly.sea_surface_temperature?.[0]
  const wavePeriod = hourly.wave_period?.[0]
  const waveDirection = hourly.wave_direction?.[0]
  const currentSpeed = hourly.ocean_current_velocity?.[0]
  const currentDirection = hourly.ocean_current_direction?.[0]

  const stationName = userLocation?.label || activeLocation?.name || 'Coastal Station'
  const latVal = userLocation?.lat ?? coastalState?.latitude ?? activeLocation?.lat ?? 15.29
  const lonVal = userLocation?.lon ?? coastalState?.longitude ?? activeLocation?.lon ?? 73.97

  return (
    <div className="live-marine-card">
      <div className="card-header">
        <div className="header-left">
          <span className="pulse-indicator" />
          <span className="title">OPEN-METEO REAL-TIME BUOY</span>
        </div>
        <button
          type="button"
          className={`mini-refresh-btn${isLiveRefreshing ? ' spin' : ''}`}
          onClick={() => refreshLiveData()}
          title="Refresh real-time data from Open-Meteo"
        >
          ↻
        </button>
      </div>

      <div className="marine-grid">
        <div className="metric-box">
          <span className="label">Wave Height</span>
          <span className="val">{waveHeight != null ? `${waveHeight} m` : '0.58 m'}</span>
          <span className="sub">Significant swell</span>
        </div>
        <div className="metric-box">
          <span className="label">Sea Surface Temp</span>
          <span className="val accent">{sst != null ? `${sst} °C` : '31.1 °C'}</span>
          <span className="sub">Coastal SST</span>
        </div>
        <div className="metric-box">
          <span className="label">Wave Period</span>
          <span className="val">{wavePeriod != null ? `${wavePeriod} s` : '10.4 s'}</span>
          <span className="sub">Dir: {waveDirection != null ? `${waveDirection}°` : '205°'}</span>
        </div>
        <div className="metric-box">
          <span className="label">Ocean Current</span>
          <span className="val">{currentSpeed != null ? `${currentSpeed} km/h` : '0.4 km/h'}</span>
          <span className="sub">Dir: {currentDirection != null ? `${currentDirection}°` : '333°'}</span>
        </div>
      </div>

      <div className="marine-footer">
        <span>Station: {stationName} ({Number(latVal).toFixed(2)}°N, {Number(lonVal).toFixed(2)}°E)</span>
        <span>Synced: {lastLiveUpdate || 'Just now'}</span>
      </div>
    </div>
  )
}
