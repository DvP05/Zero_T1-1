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
        <span>Tactical Legend</span>
        <span className="chevron">{open ? '▾' : '▴'}</span>
      </button>

      {open && (
        <div className="legend-card">
          <div className="legend-grid">
            <div className="legend-item">
              <span className="sw" style={{ background: '#10b981' }} /> Sector · LOW RISK
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#eab308' }} /> Sector · MODERATE
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#f97316' }} /> Sector · HIGH RISK
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#f43f5e' }} /> Sector · CRITICAL
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#0ea5e9' }} /> Hydrodynamic Inundation (0.3m-1.2m)
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#e11d48' }} /> Severe Flood Pool (&gt;1.2m)
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#10b981' }} /> Evacuation Expressway (Passable)
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#f43f5e', border: '1px dashed #ffffff' }} /> Submerged Arterial (Cut Off)
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#ec4899' }} /> Emergency Trauma Hospital / ICU
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#10b981' }} /> High-Ground Evacuation Shelter
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#f97316' }} /> Aquatic Rescue & Fire HQ
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#eab308' }} /> 220kV Grid Substation
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#06b6d4' }} /> Potable Water Treatment Plant
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#14b8a6' }} /> Inundation Dewatering Pump
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#a855f7' }} /> Coastguard Maritime Terminal
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#06b6d4', borderRadius: '50%' }} /> Live Buoy & Ocean Sensor
            </div>
            <div className="legend-item">
              <span className="sw" style={{ background: '#ffffff', border: '2px solid #f43f5e', borderRadius: '50%' }} /> SOS Distress Beacon
            </div>
            {isoZones.length > 0 && (
              <div className="legend-item iso-alert">
                ⚠ Isolated Sectors: {isoZones.join(', ')}
              </div>
            )}
            {showSim && (
              <div className="legend-item">
                <span className="sw" style={{ background: '#c084fc' }} /> What-If Storm Projection
              </div>
            )}
            {selectedEvent && (
              <div className="legend-item highlight">
                EPICENTER {selectedEvent.event_id} · {(selectedEvent.confidence * 100).toFixed(0)}% Conf
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
