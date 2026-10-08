import { useTidalis } from '../store'
import { useState } from 'react'

export default function SOSPanel() {
  const sosTickets = useTidalis((s) => s.sosTickets)
  const submitSosTicket = useTidalis((s) => s.submitSosTicket)
  const updateSosTicketStatus = useTidalis((s) => s.updateSosTicketStatus)
  const [showForm, setShowForm] = useState(false)

  const userLocation = useTidalis((s) => s.userLocation)
  const activeLocation = useTidalis((s) => s.activeLocation)

  const defaultLat = userLocation?.lat ?? activeLocation?.lat ?? 15.29
  const defaultLon = userLocation?.lon ?? activeLocation?.lon ?? 73.97

  // Demo form state
  const [form, setForm] = useState({
    name: '', phone: '', people_count: 1, 
    has_children: false, has_elderly: false, medical_emergency: false,
    message: '', latitude: defaultLat, longitude: defaultLon
  })

  const handleSimulateSOS = async (e) => {
    e.preventDefault()
    // Add some random jitter to coords so they don't stack perfectly
    const payload = {
      ...form,
      latitude: form.latitude + (Math.random() - 0.5) * 0.05,
      longitude: form.longitude + (Math.random() - 0.5) * 0.05,
      people_count: parseInt(form.people_count, 10)
    }
    await submitSosTicket(payload)
    setShowForm(false)
  }

  if (showForm) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
          <div style={{ fontFamily: 'var(--mono)', color: 'var(--text-hi)' }}>SIMULATE INCOMING SOS</div>
          <button className="btn" style={{ padding: '4px 8px' }} onClick={() => setShowForm(false)}>Cancel</button>
        </div>
        <form onSubmit={handleSimulateSOS} style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', paddingRight: '10px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <input className="copilot-input" style={{ width: '100%', padding: '8px', background: 'var(--panel-2)', border: '1px solid var(--border)', color: 'var(--text-hi)', borderRadius: '6px' }} placeholder="Name" value={form.name} onChange={e => setForm({...form, name: e.target.value})} required />
            <input className="copilot-input" style={{ width: '100%', padding: '8px', background: 'var(--panel-2)', border: '1px solid var(--border)', color: 'var(--text-hi)', borderRadius: '6px' }} placeholder="Phone" value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} required />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <div className="label" style={{ fontSize: '9px', marginBottom: '4px' }}>Base Latitude</div>
              <input type="number" step="0.01" className="copilot-input" style={{ width: '100%', padding: '8px', background: 'var(--panel-2)', border: '1px solid var(--border)', color: 'var(--text-hi)', borderRadius: '6px' }} value={form.latitude} onChange={e => setForm({...form, latitude: parseFloat(e.target.value)})} />
            </div>
            <div>
              <div className="label" style={{ fontSize: '9px', marginBottom: '4px' }}>Base Longitude</div>
              <input type="number" step="0.01" className="copilot-input" style={{ width: '100%', padding: '8px', background: 'var(--panel-2)', border: '1px solid var(--border)', color: 'var(--text-hi)', borderRadius: '6px' }} value={form.longitude} onChange={e => setForm({...form, longitude: parseFloat(e.target.value)})} />
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '15px', alignItems: 'center', background: 'var(--panel-2)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-soft)' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text)' }}>
              Count: <input type="number" min="1" max="50" style={{ width: '50px', background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-hi)', padding: '2px 6px', borderRadius: '4px' }} value={form.people_count} onChange={e => setForm({...form, people_count: e.target.value})} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text)' }}>
              <input type="checkbox" checked={form.has_children} onChange={e => setForm({...form, has_children: e.target.checked})} /> Children
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text)' }}>
              <input type="checkbox" checked={form.has_elderly} onChange={e => setForm({...form, has_elderly: e.target.checked})} /> Elderly
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--red)' }}>
              <input type="checkbox" checked={form.medical_emergency} onChange={e => setForm({...form, medical_emergency: e.target.checked})} /> Medical
            </label>
          </div>
          
          <textarea style={{ width: '100%', padding: '8px', background: 'var(--panel-2)', border: '1px solid var(--border)', color: 'var(--text-hi)', borderRadius: '6px', minHeight: '60px', fontFamily: 'var(--sans)', fontSize: '12px' }} placeholder="Message / Details..." value={form.message} onChange={e => setForm({...form, message: e.target.value})} />
          
          <button type="submit" className="btn" style={{ marginTop: '5px', background: 'var(--red-dim)', borderColor: 'var(--red)', color: 'var(--red)' }}>
            DROP SOS PIN (TRIAGE)
          </button>
        </form>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '10px' }}>
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '13px', color: 'var(--text-hi)', fontWeight: 'bold' }}>
            Topographical SOS Triage
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            Active Tickets: {sosTickets.filter(t => t.status !== 'RESCUED').length}
          </div>
        </div>
        <button className="btn" onClick={() => setShowForm(true)}>+ Simulate SOS</button>
      </div>

      {sosTickets.length === 0 ? (
        <div className="empty-state">NO ACTIVE DISTRESS SIGNALS</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto' }}>
          {sosTickets.map(t => (
            <div key={t.ticket_id} style={{
              background: 'var(--panel-2)',
              border: '1px solid',
              borderColor: t.status === 'RESCUED' ? 'var(--green)' : t.urgency === 'CRITICAL' ? 'rgba(251, 113, 133, 0.5)' : t.urgency === 'HIGH' ? 'rgba(251, 191, 36, 0.4)' : 'var(--border-soft)',
              borderRadius: '8px',
              padding: '12px',
              opacity: t.status === 'RESCUED' ? 0.6 : 1
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: '12px', color: 'var(--text-hi)' }}>
                  {t.ticket_id} • {t.name} ({t.people_count} pax)
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <span style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--panel)' }}>{t.status}</span>
                  <span className={`sev ${t.urgency}`} style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px' }}>
                    {t.urgency}
                  </span>
                </div>
              </div>
              
              <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '8px' }}>
                <span style={{ color: t.water_margin_m < 0 ? 'var(--red)' : 'var(--text)' }}>
                  Elev: {t.elevation_m}m | Flood Depth: {t.predicted_flood_depth_m}m | Margin: {t.water_margin_m}m
                </span>
                <br />
                {t.triage_reason}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px dashed var(--border)', paddingTop: '8px' }}>
                <div style={{ fontSize: '11px', color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                  <span style={{ color: 'var(--muted)' }}>Method:</span> {t.rescue_method.replace('_', ' ')}
                  <span style={{ marginLeft: '10px', color: 'var(--muted)' }}>ETA:</span> {t.eta_minutes}m
                </div>
                {t.status === 'PENDING' && (
                  <button className="copy-btn" style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }} onClick={() => updateSosTicketStatus(t.ticket_id, 'DISPATCHED')}>DISPATCH</button>
                )}
                {t.status === 'DISPATCHED' && (
                  <button className="copy-btn" style={{ borderColor: 'var(--amber)', color: 'var(--amber)' }} onClick={() => updateSosTicketStatus(t.ticket_id, 'RESCUED')}>MARK RESCUED</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
