import { useState } from 'react'
import { useTidalis } from '../../store'

export default function MapLegend() {
  const [open, setOpen] = useState(false)
  const snapshot = useTidalis((s) => s.snapshot)
  const events = useTidalis((s) => s.events)
  const selectedEventId = useTidalis((s) => s.selectedEventId)
  const layers = useTidalis((s) => s.layers)
  const simulation = useTidalis((s) => s.simulation)

  const selectedEvent = events.find((e) => e.event_id === selectedEventId)
  const showSim = layers.simulation && simulation?.steps?.length > 0
  const isoZones = snapshot?.isolation?.isolated_zones ?? []

  return (
    <div className={`map-legend-dock${open ? ' expanded' : ''}`}>
      <button
        type="button"
        className="legend-toggle-pill"
        onClick={() => setOpen(!open)}
        title="Toggle Map Symbology Legend"
      >
        <span className="dot-key" />
        <span>Map Legend</span>
        <span className="chevron">{open ? '▾' : '▴'}</span>
      </button>

      {open && (
        <div className="legend-card">
          <div className="legend-grid">
            <div className="legend-item">
              <span className="sw" style={{ background: '#34d399' }} /> Zone · LOW
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#fbbf24' }} /> Zone · MODERATE
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#fb923c' }} /> Zone · HIGH
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#fb7185' }} /> Zone · CRITICAL
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#0ea5e9' }} /> Rising Flood Water
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#fb7185' }} /> Submerged Road
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#22d3ee' }} /> Critical Facility
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#ffffff', border: '1px solid #fb7185' }} /> SOS Beacon
            </div>
            {isoZones.length > 0 && (
              <div className="legend-item iso-alert">
                ⚠ Isolated: {isoZones.join(', ')}
              </div>
            )}
            {showSim && (
              <div className="legend-item">
                <span className="sw" style={{ background: '#a78bfa' }} /> What-If projection
              </div>
            )}
            {selectedEvent && (
              <div className="legend-item highlight">
                EVT {selectedEvent.event_id} · {(selectedEvent.confidence * 100).toFixed(0)}% conf
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
