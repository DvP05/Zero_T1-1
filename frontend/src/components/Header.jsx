import { useState } from 'react'
import { useTidalis, COASTAL_DISTRICTS } from '../store'

const COASTAL_PRESETS = [
  { name: 'Puri Beach, Odisha', lat: 19.8135, lon: 85.8312, coast: 'Bay of Bengal' },
  { name: 'Diu Island, Gujarat', lat: 20.7144, lon: 70.9874, coast: 'Arabian Sea' },
  { name: 'Kanyakumari Cape, Tamil Nadu', lat: 8.0883, lon: 77.5385, coast: 'Indian Ocean' },
  { name: 'Alappuzha Backwaters, Kerala', lat: 9.4981, lon: 76.3388, coast: 'Arabian Sea' },
  { name: 'Paradip Deepwater Port, Odisha', lat: 20.3165, lon: 86.6114, coast: 'Bay of Bengal' },
  { name: 'Digha Coastal Beach, West Bengal', lat: 21.6266, lon: 87.5074, coast: 'Bay of Bengal' },
]

export default function Header() {
  const health = useTidalis((s) => s.health)
  const coastalState = useTidalis((s) => s.coastalState)
  const marineData = useTidalis((s) => s.marineData)
  const lastLiveUpdate = useTidalis((s) => s.lastLiveUpdate)
  const isLiveRefreshing = useTidalis((s) => s.isLiveRefreshing)
  const refreshLiveData = useTidalis((s) => s.refreshLiveData)
  const online = useTidalis((s) => s.online)
  const activeLocation = useTidalis((s) => s.activeLocation)
  const customCoastline = useTidalis((s) => s.customCoastline)
  const switchDistrict = useTidalis((s) => s.switchDistrict)
  const geo = useTidalis((s) => s.geo)

  // Custom coordinate modal state
  const [showCustomModal, setShowCustomModal] = useState(false)
  const [customName, setCustomName] = useState(customCoastline?.name || 'Puri Coastal Sector, Odisha')
  const [customLat, setCustomLat] = useState(customCoastline?.lat ? String(customCoastline.lat) : '19.8135')
  const [customLon, setCustomLon] = useState(customCoastline?.lon ? String(customCoastline.lon) : '85.8312')
  const [customError, setCustomError] = useState('')

  const currentDistrictId =
    activeLocation?.districtId ||
    geo?.meta?.zone_id ||
    'goa'

  const waveHeight = marineData?.hourly?.wave_height?.[0]
  const sst = marineData?.hourly?.sea_surface_temperature?.[0]
  const currentSpeed = marineData?.hourly?.ocean_current_velocity?.[0]

  const handleSelectDistrict = (val) => {
    if (val === '__configure_custom__') {
      setShowCustomModal(true)
      return
    }
    if (val === 'custom') {
      if (!customCoastline) {
        setShowCustomModal(true)
      } else {
        switchDistrict('custom')
      }
      return
    }
    switchDistrict(val)
  }

  const validateIndianCoastalCoords = (latNum, lonNum) => {
    if (isNaN(latNum) || isNaN(lonNum)) {
      return 'Latitude and Longitude must be valid numbers.'
    }
    if (latNum < 6.0 || latNum > 24.5) {
      return `Latitude (${latNum.toFixed(2)}°N) is outside the Indian coastal boundary (6.0°N to 24.5°N).`
    }
    if (lonNum < 68.0 || lonNum > 90.5) {
      return `Longitude (${lonNum.toFixed(2)}°E) is outside the Indian coastal boundary (68.0°E to 90.5°E).`
    }
    return null
  }

  const handleDeployCustom = (e) => {
    if (e) e.preventDefault()
    const latNum = parseFloat(customLat)
    const lonNum = parseFloat(customLon)
    const err = validateIndianCoastalCoords(latNum, lonNum)
    if (err) {
      setCustomError(err)
      return
    }
    setCustomError('')
    const name = customName.trim() || `Custom Indian Coastline (${latNum.toFixed(2)}°N, ${lonNum.toFixed(2)}°E)`
    switchDistrict('custom', { lat: latNum, lon: lonNum, name })
    setShowCustomModal(false)
  }

  const applyPreset = (preset) => {
    setCustomName(preset.name)
    setCustomLat(String(preset.lat))
    setCustomLon(String(preset.lon))
    setCustomError('')
  }

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <h1>DAM-N</h1>
          <span className="tagline">AI-Powered Coastal Digital Intelligence</span>
        </div>

        {/* Operational District Switcher */}
        <div className="theater-pill" title="Operational District & Administrative Boundary">
          <span className="theater-dot" />
          <select
            className="theater-select"
            value={currentDistrictId}
            onChange={(e) => handleSelectDistrict(e.target.value)}
            aria-label="Operational District"
          >
            <optgroup label="Western Arabian Sea Coast">
              <option value="goa">Goa Coastal District</option>
              <option value="mangaluru">Mangaluru Coastal District</option>
              <option value="mumbai">Mumbai Harbor District</option>
              <option value="kochi">Kochi Port District</option>
            </optgroup>
            <optgroup label="Eastern Bay of Bengal Coast">
              <option value="chennai">Chennai Coastal District</option>
              <option value="kolkata">Kolkata Sundarbans Estuary</option>
              <option value="visakhapatnam">Visakhapatnam Harbor District</option>
            </optgroup>
            <optgroup label="Custom Indian Coastline">
              <option value="custom">
                {customCoastline ? `📍 ${customCoastline.name}` : '⚙️ Custom Indian Coastline...'}
              </option>
              <option value="__configure_custom__">+ Configure Custom Coordinates...</option>
            </optgroup>
          </select>
          <button
            type="button"
            className="theater-custom-btn"
            onClick={() => setShowCustomModal(true)}
            title="Configure custom Indian coastal coordinates"
          >
            ⚙️ Custom
          </button>
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
          onClick={() => refreshLiveData()}
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

      {/* Custom Coastline Modal */}
      {showCustomModal && (
        <div className="token-modal-overlay" onClick={() => setShowCustomModal(false)}>
          <div
            className="token-modal"
            style={{ width: '480px' }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-header">
              <span>DEPLOY CUSTOM COASTLINE TWIN</span>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowCustomModal(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleDeployCustom} className="modal-body">
              <p className="token-desc">
                Deploy real-time Open-Meteo marine & weather telemetry, topological defenses, and 3D digital-twin layers for any coastal location along the Indian coastline.
              </p>

              <div>
                <span className="field-label">Quick Coastal Presets:</span>
                <div className="preset-chip-list">
                  {COASTAL_PRESETS.map((p) => (
                    <button
                      key={p.name}
                      type="button"
                      className="preset-chip"
                      onClick={() => applyPreset(p)}
                    >
                      {p.name.split(',')[0]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="field-label">Coastline / City Name</label>
                <input
                  type="text"
                  className="token-input"
                  placeholder="e.g. Puri Beach, Odisha"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                />
              </div>

              <div className="custom-input-grid">
                <div>
                  <label className="field-label">Latitude (°N: 6.0 to 24.5)</label>
                  <input
                    type="number"
                    step="0.0001"
                    className="token-input"
                    placeholder="19.8135"
                    value={customLat}
                    onChange={(e) => {
                      setCustomLat(e.target.value)
                      setCustomError('')
                    }}
                    required
                  />
                </div>
                <div>
                  <label className="field-label">Longitude (°E: 68.0 to 90.5)</label>
                  <input
                    type="number"
                    step="0.0001"
                    className="token-input"
                    placeholder="85.8312"
                    value={customLon}
                    onChange={(e) => {
                      setCustomLon(e.target.value)
                      setCustomError('')
                    }}
                    required
                  />
                </div>
              </div>

              {customError && (
                <div style={{ color: '#f43f5e', fontSize: '11px', fontFamily: 'var(--mono)', background: 'rgba(244, 63, 94, 0.1)', padding: '6px 10px', borderRadius: '4px', border: '1px solid rgba(244, 63, 94, 0.3)' }}>
                  ⚠️ {customError}
                </div>
              )}

              <div className="modal-footer" style={{ marginTop: '12px' }}>
                <button
                  type="button"
                  className="preset-chip"
                  onClick={() => setShowCustomModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="save-token-btn"
                  style={{ background: 'var(--accent)', color: '#021019', fontWeight: 'bold' }}
                >
                  Deploy Digital Twin 🚀
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
