import { useTidalis } from '../store'

export default function MitigationPanel() {
  const mitigationPlan = useTidalis((s) => s.mitigationPlan)
  const selectedEventId = useTidalis((s) => s.selectedEventId)

  if (!selectedEventId) {
    return <div className="empty-state">SELECT AN EVENT TO VIEW MITIGATION PLAN</div>
  }

  if (!mitigationPlan) {
    return <div className="empty-state">GENERATING PREVENTATIVE MITIGATION PLAN...</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', height: '100%', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '10px' }}>
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '13px', color: 'var(--text-hi)', fontWeight: 'bold' }}>
            Actionable Mitigation Plan
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            Estimated Risk Reduction: <span style={{ color: 'var(--green)' }}>{(mitigationPlan.estimated_risk_reduction * 100).toFixed(1)}%</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <div className="metric" style={{ padding: '4px 8px' }}>
            <span className="label" style={{ fontSize: '8px' }}>Total</span>
            <span className="value" style={{ fontSize: '14px', marginLeft: '6px' }}>{mitigationPlan.total_suggestions}</span>
          </div>
          <div className="metric" style={{ padding: '4px 8px', borderColor: 'rgba(251, 113, 133, 0.4)', background: 'var(--red-dim)' }}>
            <span className="label" style={{ fontSize: '8px', color: 'var(--red)' }}>Immediate</span>
            <span className="value alert" style={{ fontSize: '14px', marginLeft: '6px' }}>{mitigationPlan.immediate_actions}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {mitigationPlan.suggestions.map((sug) => (
          <div key={sug.id} style={{
            background: 'var(--panel-2)',
            border: '1px solid',
            borderColor: sug.priority === 'IMMEDIATE' ? 'rgba(251, 113, 133, 0.5)' : sug.priority === 'HIGH' ? 'rgba(251, 191, 36, 0.4)' : 'var(--border-soft)',
            borderRadius: '8px',
            padding: '12px',
            position: 'relative',
            overflow: 'hidden'
          }}>
            {sug.priority === 'IMMEDIATE' && (
              <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: 'var(--red)' }} />
            )}
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div style={{ fontFamily: 'var(--sans)', fontSize: '13px', color: 'var(--text-hi)', fontWeight: '600' }}>
                {sug.action}
              </div>
              <span className={`sev ${sug.priority === 'IMMEDIATE' ? 'CRITICAL' : sug.priority}`} style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px', marginLeft: '10px' }}>
                {sug.priority}
              </span>
            </div>
            
            <div style={{ fontSize: '12px', color: 'var(--text)', lineHeight: '1.4', marginBottom: '10px' }}>
              {sug.description}
            </div>
            
            <div style={{ display: 'flex', gap: '15px', borderTop: '1px dashed var(--border)', paddingTop: '10px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span className="label" style={{ fontSize: '9px' }}>Vector</span>
                <span style={{ fontSize: '11px', color: 'var(--accent)', fontFamily: 'var(--mono)' }}>{sug.threat_vector.replace(/_/g, ' ')}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span className="label" style={{ fontSize: '9px' }}>Time to Deploy</span>
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
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
