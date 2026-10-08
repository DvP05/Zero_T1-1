import { useTidalis } from '../store'

const TYPE_COLORS = {
  HABITAT: '#a78bfa',
  FISHERY: '#22d3ee',
  PORT: '#fbbf24',
  BEACH: '#34d399',
  POPULATION: '#fb7185',
  INDUSTRY: '#f97316',
  TOURISM: '#e879f9',
  CUSTOM_ASSET: '#94a3b8',
}

export default function ExposurePanel() {
  const exposures = useTidalis((s) => s.exposures)

  if (exposures.length === 0) {
    return <div className="empty-state">NO ASSETS WITHIN ESTIMATED EXPOSURE RANGE</div>
  }

  return (
    <div className="tile-grid">
      {exposures.map((exp) => (
        <div className="tile" key={exp.asset_id}>
          <div className="h" style={{ color: TYPE_COLORS[exp.asset_type] ?? '#94a3b8' }}>
            ▮ {exp.asset_type}
          </div>
          <div className="v">
            {exp.asset_name}
          </div>
          <div className="d">
            exposure <b style={{ color: 'var(--accent)' }}>{(exp.exposure_score * 100).toFixed(0)}%</b>
            {' '}· {exp.distance_km.toFixed(1)} km {exp.direction}
          </div>
        </div>
      ))}
    </div>
  )
}