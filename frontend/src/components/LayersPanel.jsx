import { useTidalis } from '../store'

const LAYER_META = [
  { id: 'zones', label: 'Flood Zones', color: 'exposure' },
  { id: 'flood', label: 'Rising Water', color: 'sensors' },
  { id: 'roads', label: 'Road Network', color: 'events' },
  { id: 'buildings', label: 'Buildings (3D)', color: 'simulation' },
  { id: 'facilities', label: 'Critical Facilities', color: 'sos' },
  { id: 'sensors', label: 'Sensor Network', color: 'sensors' },
  { id: 'events', label: 'Detected Events', color: 'events' },
  { id: 'exposure', label: 'Exposure Zones', color: 'exposure' },
  { id: 'simulation', label: 'What-If Projection', color: 'simulation' },
  { id: 'sos', label: 'Topographical SOS', color: 'sos' },
]

export default function LayersPanel() {
  const layers = useTidalis((s) => s.layers)
  const toggle = useTidalis((s) => s.toggleLayer)

  return (
    <div className="panel">
      <div className="panel-header"><span>Layers</span></div>
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