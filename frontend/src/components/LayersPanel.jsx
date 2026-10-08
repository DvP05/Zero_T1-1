import { useTidalis } from '../store'

const LAYER_META = [
  { id: 'flood', label: 'Hydrodynamic Inundation', color: 'sensors' },
  { id: 'zones', label: 'Hazard Sectors', color: 'exposure' },
  { id: 'roads', label: 'Roads & Evacuation Routes', color: 'events' },
  { id: 'facilities', label: 'Critical Facilities', color: 'sos' },
  { id: 'buildings', label: '3D City Buildings', color: 'simulation' },
  { id: 'sensors', label: 'Buoys & IoT Telemetry', color: 'sensors' },
  { id: 'events', label: 'Incident Epicenters', color: 'events' },
  { id: 'exposure', label: 'Exposure Buffer', color: 'exposure' },
  { id: 'simulation', label: 'What-If Storm Projection', color: 'simulation' },
  { id: 'sos', label: 'SOS Distress Signals', color: 'sos' },
]

export default function LayersPanel() {
  const layers = useTidalis((s) => s.layers)
  const toggle = useTidalis((s) => s.toggleLayer)

  return (
    <div className="panel">
      <div className="panel-header">
        <span>Tactical Overlays</span>
      </div>
      <div className="panel-body">
        {LAYER_META.map((l) => (
          <div key={l.id} className="layer-toggle">
            <label>
              <span className={`switch-dot ${l.color}`} />
              {l.label}
            </label>
            <div
              className={`switch${layers[l.id] ? ' on' : ''}`}
              role="switch"
              aria-checked={layers[l.id]}
              aria-label={l.label}
              onClick={() => toggle(l.id)}
            />
          </div>
        ))}
      </div>
    </div>
  )
}