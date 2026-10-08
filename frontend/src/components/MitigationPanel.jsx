import { useState } from 'react'
import { useTidalis } from '../store'

export default function MitigationPanel() {
  const mitigationPlan = useTidalis((s) => s.mitigationPlan)
  const selectedEventId = useTidalis((s) => s.selectedEventId)
  const snapshot = useTidalis((s) => s.snapshot)
  const flyToTarget = useTidalis((s) => s.flyToTarget)
  const authorizeBottleneckDefense = useTidalis((s) => s.authorizeBottleneckDefense)
  const [loadingAction, setLoadingAction] = useState(null)

  if (!selectedEventId) {
    return <div className="empty-state">SELECT AN EVENT TO VIEW MITIGATION PLAN</div>
  }

  if (!mitigationPlan) {
    return <div className="empty-state">GENERATING PREVENTATIVE MITIGATION PLAN...</div>
  }

  const networkIntegrity = snapshot?.isolation?.network_integrity ?? 1.0
  const bottlenecks = snapshot?.isolation?.bottlenecks ?? []

  const handleToggleDefense = async (sug) => {
    setLoadingAction(sug.id)
    try {
      await authorizeBottleneckDefense(sug.id)
    } finally {
      setLoadingAction(null)
    }
  }

  const handleInspect = (sug) => {
    if (sug.coordinates && sug.coordinates.length >= 2) {
      flyToTarget({
        lat: sug.coordinates[1],
        lon: sug.coordinates[0],
        zoom: 15.2,
        pitch: 58,
        bearing: -20,
      })
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', height: '100%', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '10px' }}>
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '13px', color: 'var(--text-hi)', fontWeight: 'bold' }}>
            Topological & Preventative Mitigation
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            Network Integrity: <span style={{ color: networkIntegrity > 0.8 ? 'var(--green)' : 'var(--amber)', fontWeight: 'bold' }}>{(networkIntegrity * 100).toFixed(0)}%</span>
            {' · '}Risk Reduction: <span style={{ color: 'var(--green)' }}>{(mitigationPlan.estimated_risk_reduction * 100).toFixed(1)}%</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <div className="metric" style={{ padding: '4px 8px' }}>
            <span className="label" style={{ fontSize: '8px' }}>Cut-Edges</span>
            <span className="value" style={{ fontSize: '14px', marginLeft: '6px', color: 'var(--amber)' }}>{bottlenecks.length}</span>
          </div>
          <div className="metric" style={{ padding: '4px 8px', borderColor: 'rgba(251, 113, 133, 0.4)', background: 'var(--red-dim)' }}>
            <span className="label" style={{ fontSize: '8px', color: 'var(--red)' }}>Immediate</span>
            <span className="value alert" style={{ fontSize: '14px', marginLeft: '6px' }}>{mitigationPlan.immediate_actions}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {mitigationPlan.suggestions.map((sug) => {
          const isDefended = sug.status === 'ACTIVE'
          return (
            <div key={sug.id} style={{
              background: sug.is_topological ? 'rgba(15, 23, 42, 0.95)' : 'var(--panel-2)',
              border: '1px solid',
              borderColor: isDefended
                ? '#10b981'
                : sug.is_topological
                ? 'rgba(251, 191, 36, 0.65)'
                : sug.priority === 'IMMEDIATE'
                ? 'rgba(251, 113, 133, 0.5)'
                : 'var(--border-soft)',
              borderRadius: '8px',
              padding: '12px',
              position: 'relative',
              overflow: 'hidden',
              boxShadow: sug.is_topological ? '0 4px 14px rgba(0,0,0,0.45)' : 'none',
            }}>
              {sug.is_topological && (
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '4px',
                  height: '100%',
                  background: isDefended ? '#10b981' : '#f59e0b',
                }} />
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {sug.is_topological && (
                    <span style={{
                      fontSize: '9px',
                      fontFamily: 'var(--mono)',
                      color: isDefended ? '#34d399' : '#fbbf24',
                      fontWeight: '700',
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                      marginBottom: '2px',
                    }}>
                      ⚡ TOPOLOGICAL BOTTLENECK DEFENSE
                    </span>
                  )}
                  <div style={{ fontFamily: 'var(--sans)', fontSize: '13px', color: 'var(--text-hi)', fontWeight: '600' }}>
                    {sug.action}
                  </div>
                </div>
                <span className={`sev ${isDefended ? 'LOW' : sug.priority === 'IMMEDIATE' ? 'CRITICAL' : sug.priority}`} style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px', marginLeft: '10px' }}>
                  {isDefended ? 'DEFENDED' : sug.priority}
                </span>
              </div>

              <div style={{ fontSize: '12px', color: 'var(--text)', lineHeight: '1.4', marginBottom: '10px' }}>
                {sug.description}
              </div>

              <div style={{ display: 'flex', gap: '15px', borderTop: '1px dashed var(--border)', paddingTop: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span className="label" style={{ fontSize: '9px' }}>Vector</span>
                  <span style={{ fontSize: '11px', color: 'var(--accent)', fontFamily: 'var(--mono)' }}>{sug.threat_vector.replace(/_/g, ' ')}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span className="label" style={{ fontSize: '9px' }}>Deploy Time</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-hi)', fontFamily: 'var(--mono)' }}>{sug.time_to_deploy}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span className="label" style={{ fontSize: '9px' }}>Cost</span>
                  <span style={{ fontSize: '11px', color: 'var(--amber)', fontFamily: 'var(--mono)' }}>{sug.estimated_cost}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                  <span className="label" style={{ fontSize: '9px' }}>Resources</span>
                  <span style={{ fontSize: '11px', color: 'var(--text)', fontFamily: 'var(--sans)' }}>{sug.resources_needed.join(', ')}</span>
                </div>

                {sug.is_topological && (
                  <div style={{ display: 'flex', gap: '8px', width: '100%', marginTop: '6px' }}>
                    <button
                      onClick={() => handleToggleDefense(sug)}
                      disabled={loadingAction === sug.id}
                      style={{
                        flex: 1,
                        background: isDefended ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.25)',
                        border: '1px solid',
                        borderColor: isDefended ? '#10b981' : '#f59e0b',
                        color: isDefended ? '#34d399' : '#fef08a',
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        fontWeight: '700',
                        cursor: 'pointer',
                        fontFamily: 'var(--mono)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {loadingAction === sug.id
                        ? 'COMMUNICATING...'
                        : isDefended
                        ? '🛡️ DEFENSE ACTIVE (STAND DOWN)'
                        : '⚡ AUTHORIZE PHYSICAL DEFENSE'}
                    </button>
                    {sug.coordinates && (
                      <button
                        onClick={() => handleInspect(sug)}
                        style={{
                          background: 'rgba(56, 189, 248, 0.15)',
                          border: '1px solid #38bdf8',
                          color: '#38bdf8',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: '600',
                          cursor: 'pointer',
                          fontFamily: 'var(--mono)',
                        }}
                      >
                        🎯 INSPECT
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

