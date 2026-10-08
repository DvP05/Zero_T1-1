import { useState } from 'react'
import { useTidalis } from '../../store'
import { MAPBOX_STYLES } from './mapboxStyles'

export default function MapHUD({ pitched, onToggle3D, onRecenter }) {
  const mapStyle = useTidalis((s) => s.mapStyle)
  const setMapStyle = useTidalis((s) => s.setMapStyle)
  const mapboxToken = useTidalis((s) => s.mapboxToken)
  const setMapboxToken = useTidalis((s) => s.setMapboxToken)

  const [showTokenModal, setShowTokenModal] = useState(false)
  const [tokenInput, setTokenInput] = useState(mapboxToken || '')
  const [tokenSaved, setTokenSaved] = useState(false)

  const handleSaveToken = (e) => {
    e.preventDefault()
    setMapboxToken(tokenInput.trim())
    setTokenSaved(true)
    setTimeout(() => {
      setTokenSaved(false)
      setShowTokenModal(false)
    }, 1200)
  }

  const hasToken = Boolean(mapboxToken && mapboxToken.startsWith('pk.'))

  return (
    <>
      <div className="map-hud-top-right">
        {/* Style Selector */}
        <div className="hud-group">
          {Object.values(MAPBOX_STYLES).map((s) => (
            <button
              key={s.id}
              type="button"
              className={`hud-btn${mapStyle === s.id ? ' active' : ''}`}
              onClick={() => setMapStyle(s.id)}
              title={s.name}
            >
              {s.id === 'dark' ? 'Dark' : s.id === 'satellite' ? 'Sat' : 'Night'}
            </button>
          ))}
        </div>

        {/* 2D / 3D Switch */}
        <button
          type="button"
          className={`hud-btn pitch-btn${pitched ? ' active' : ''}`}
          onClick={onToggle3D}
          title={pitched ? 'Switch to 2D Top-Down View' : 'Switch to 3D Digital Twin View'}
        >
          {pitched ? '3D Active' : '2D Map'}
        </button>

        {/* Recenter */}
        <button
          type="button"
          className="hud-btn icon-btn"
          onClick={onRecenter}
          title="Recenter Camera on Operations Area"
        >
          ⌖ Recenter
        </button>

        {/* Token Config Button */}
        <button
          type="button"
          className={`hud-btn icon-btn${!hasToken ? ' warn' : ''}`}
          onClick={() => setShowTokenModal(true)}
          title={hasToken ? 'Mapbox Token Configured' : 'Configure Mapbox Token'}
        >
          {hasToken ? '🔑 Mapbox' : '⚠️ Token'}
        </button>
      </div>

      {/* Mapbox Token Modal */}
      {showTokenModal && (
        <div className="token-modal-overlay" onClick={() => setShowTokenModal(false)}>
          <div className="token-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span>Mapbox Configuration</span>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowTokenModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSaveToken} className="modal-body">
              <p className="token-desc">
                Enter your Mapbox Public Access Token (starts with <code>pk.ey...</code>) to enable high-resolution satellite imagery, 3D terrain elevation, and atmospheric rendering.
              </p>
              <input
                type="text"
                className="token-input"
                placeholder="pk.eyJ1..."
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                autoFocus
              />
              <div className="modal-footer">
                <a
                  href="https://account.mapbox.com/access-tokens/"
                  target="_blank"
                  rel="noreferrer"
                  className="token-link"
                >
                  Get a free token ↗
                </a>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    className="btn ghost"
                    onClick={() => setShowTokenModal(false)}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn primary">
                    {tokenSaved ? '✓ Saved!' : 'Apply Token'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
