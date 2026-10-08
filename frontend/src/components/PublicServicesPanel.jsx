import { useState, useMemo } from 'react'
import { useTidalis } from '../store'

const CATEGORIES = [
  { id: 'all', label: 'All Services', icon: '🏛️' },
  { id: 'health', label: 'Hospitals', icon: '🏥' },
  { id: 'shelter', label: 'Shelters', icon: '🛡️' },
  { id: 'emergency', label: 'Rescue & Police', icon: '🚒' },
  { id: 'utility', label: 'Power & Water', icon: '⚡' },
  { id: 'transport', label: 'Ports & Logistics', icon: '🚢' },
]

export default function PublicServicesPanel() {
  const geo = useTidalis((s) => s.geo)
  const snapshot = useTidalis((s) => s.snapshot)
  const flyToTarget = useTidalis((s) => s.flyToTarget)
  const selectZone = useTidalis((s) => s.selectZone)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  const threatenedSet = useMemo(() => {
    return new Set((snapshot?.zones ?? []).flatMap((z) => z.facilities_threatened ?? []))
  }, [snapshot])

  const facilities = useMemo(() => {
    const raw = geo?.layers?.facilities?.features || []
    return raw.map((f) => {
      const p = f.properties || {}
      const isThreatened = threatenedSet.has(p.name)
      return {
        ...f,
        properties: {
          ...p,
          threatened: isThreatened,
        },
      }
    })
  }, [geo, threatenedSet])

  const filtered = useMemo(() => {
    return facilities.filter((f) => {
      const p = f.properties
      if (search.trim()) {
        const query = search.toLowerCase()
        const matchName = (p.name || '').toLowerCase().includes(query)
        const matchKind = (p.kind || '').toLowerCase().includes(query)
        const matchZone = (p.zone_id || '').toLowerCase().includes(query)
        const matchService = (p.service_type || '').toLowerCase().includes(query)
        if (!matchName && !matchKind && !matchZone && !matchService) return false
      }

      if (filter === 'health') return p.kind === 'hospital'
      if (filter === 'shelter') return p.kind === 'shelter'
      if (filter === 'emergency') return p.kind === 'fire_station' || p.kind === 'police'
      if (filter === 'utility') return p.kind === 'substation' || p.kind === 'power_substation' || p.kind === 'water_plant' || p.kind === 'water_treatment' || p.kind === 'pumping_station' || p.kind === 'drainage_pump'
      if (filter === 'transport') return p.kind === 'port' || p.kind === 'port_terminal'
      return true
    })
  }, [facilities, filter, search])

  const stats = useMemo(() => {
    const total = facilities.length
    const threatened = facilities.filter((f) => f.properties.threatened).length
    const operational = total - threatened
    return { total, threatened, operational }
  }, [facilities])

  const handleLocate = (f) => {
    const coords = f.geometry?.coordinates
    if (coords && coords.length >= 2) {
      flyToTarget({
        lng: coords[0],
        lat: coords[1],
        zoom: 16.5,
        pitch: 55,
        bearing: -14,
      })
      if (f.properties?.zone_id) {
        selectZone(f.properties.zone_id)
      }
    }
  }

  return (
    <div className="panel public-services-panel">
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-title">Public Services & Critical Infrastructure</span>
          <span className="badge badge-info">{stats.total} Mapped</span>
        </div>
      </div>

      <div className="panel-body">
        {/* KPI Summary Header */}
        <div className="ps-kpi-row">
          <div className="ps-kpi-card">
            <span className="ps-kpi-val">{stats.total}</span>
            <span className="ps-kpi-lbl">Total Facilities</span>
          </div>
          <div className="ps-kpi-card ok">
            <span className="ps-kpi-val">{stats.operational}</span>
            <span className="ps-kpi-lbl">Operational</span>
          </div>
          <div className={`ps-kpi-card ${stats.threatened > 0 ? 'alert' : ''}`}>
            <span className="ps-kpi-val">{stats.threatened}</span>
            <span className="ps-kpi-lbl">Threatened</span>
          </div>
        </div>

        {/* Filter Chips & Search Bar */}
        <div className="ps-filter-bar">
          <input
            type="text"
            className="ps-search-input"
            placeholder="Search hospitals, shelters, power, zones..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="ps-category-pills">
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`ps-pill ${filter === c.id ? 'active' : ''}`}
                onClick={() => setFilter(c.id)}
              >
                <span>{c.icon}</span>
                <span>{c.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Facilities List */}
        <div className="ps-facility-list">
          {filtered.length === 0 ? (
            <div className="empty-state">No facilities match current filters.</div>
          ) : (
            filtered.map((f) => {
              const p = f.properties
              const isTh = p.threatened
              return (
                <div key={p.name} className={`ps-card ${isTh ? 'threatened' : 'operational'}`}>
                  <div className="ps-card-header">
                    <div className="ps-card-title-row">
                      <span className="ps-icon">{p.icon || '📍'}</span>
                      <div className="ps-title-box">
                        <div className="ps-name">{p.name}</div>
                        <div className="ps-service-type">{p.service_type || p.kind}</div>
                      </div>
                    </div>
                    <span className={`ps-status-badge ${isTh ? 'alert' : 'ok'}`}>
                      {isTh ? 'THREATENED' : 'OPERATIONAL'}
                    </span>
                  </div>

                  <div className="ps-meta-grid">
                    <div className="ps-meta-item">
                      <span className="ps-meta-lbl">Zone</span>
                      <span className="ps-meta-val">Zone {p.zone_id}</span>
                    </div>
                    <div className="ps-meta-item">
                      <span className="ps-meta-lbl">Elevation</span>
                      <span className="ps-meta-val">{p.elevation_m != null ? `${p.elevation_m} m MSL` : '—'}</span>
                    </div>
                    <div className="ps-meta-item">
                      <span className="ps-meta-lbl">Capacity</span>
                      <span className="ps-meta-val">{p.capacity || '—'}</span>
                    </div>
                    <div className="ps-meta-item">
                      <span className="ps-meta-lbl">Criticality</span>
                      <span className={`ps-meta-val ${p.criticality === 'tier_1' || (typeof p.criticality === 'number' && p.criticality >= 0.85) ? 'crit' : ''}`}>
                        {typeof p.criticality === 'string'
                          ? p.criticality.replace('_', ' ').toUpperCase()
                          : typeof p.criticality === 'number'
                          ? (p.criticality >= 0.85 ? 'TIER 1 (CRITICAL)' : 'TIER 2 (STANDARD)')
                          : 'STANDARD'}
                      </span>
                    </div>
                  </div>

                  <div className="ps-card-actions">
                    <button
                      type="button"
                      className="ps-fly-btn"
                      onClick={() => handleLocate(f)}
                      title={`Fly camera to ${p.name}`}
                    >
                      <span>📍 Fly to Location (3D)</span>
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
