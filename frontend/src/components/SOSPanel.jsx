import { useState, useId } from 'react'
import { useTidalis } from '../store'

const PRESETS = [
  {
    label: '🌊 Lowland Family',
    name: 'Sunita Gaonkar & Family',
    phone: '+91 98221 45678',
    people_count: 4,
    has_children: true,
    has_elderly: false,
    medical_emergency: false,
    message: 'Water overtopping ground floor patio, 0.4m deep and rising.',
  },
  {
    label: '🏥 Elderly Medical Urgent',
    name: "Francis D'Souza",
    phone: '+91 98450 11234',
    people_count: 1,
    has_children: false,
    has_elderly: true,
    medical_emergency: true,
    message: 'Oxygen concentrator without power, water at door step.',
  },
  {
    label: '🏢 Commercial Shopfront',
    name: 'Rajesh Coastal Mart',
    phone: '+91 99012 33456',
    people_count: 3,
    has_children: false,
    has_elderly: false,
    medical_emergency: false,
    message: 'Cut off by flooded culvert, seeking boat evacuation to high ground.',
  },
]

export default function SOSPanel() {
  const sosTickets = useTidalis((s) => s.sosTickets)
  const submitSosTicket = useTidalis((s) => s.submitSosTicket)
  const updateSosTicketStatus = useTidalis((s) => s.updateSosTicketStatus)
  const flyToTarget = useTidalis((s) => s.flyToTarget)

  const userLocation = useTidalis((s) => s.userLocation)
  const activeLocation = useTidalis((s) => s.activeLocation)

  const defaultLat = userLocation?.lat ?? activeLocation?.lat ?? 15.2993
  const defaultLon = userLocation?.lon ?? activeLocation?.lon ?? 73.97

  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState(null)

  const [form, setForm] = useState({
    name: '',
    phone: '',
    people_count: 1,
    has_children: false,
    has_elderly: false,
    medical_emergency: false,
    message: '',
    latitude: defaultLat,
    longitude: defaultLon,
    addScatter: false,
  })

  const [touched, setTouched] = useState({})

  // ---------- Form Validation Logic -----------------------------------------
  const validate = (values) => {
    const errs = {}

    // Name
    const trimmedName = (values.name || '').trim()
    if (!trimmedName) {
      errs.name = 'Full name or contact person is required'
    } else if (trimmedName.length < 2) {
      errs.name = 'Name must be at least 2 characters long'
    } else if (trimmedName.length > 60) {
      errs.name = 'Name cannot exceed 60 characters'
    } else if (!/[a-zA-Z\u0900-\u097F]/.test(trimmedName)) {
      errs.name = 'Name must contain valid alphabetic characters'
    }

    // Phone
    const trimmedPhone = (values.phone || '').trim()
    const digitsOnly = trimmedPhone.replace(/\D/g, '')
    if (!trimmedPhone) {
      errs.phone = 'Contact phone number is required'
    } else if (!/^\+?[0-9\s\-()]+$/.test(trimmedPhone)) {
      errs.phone = 'Phone number contains invalid symbols'
    } else if (digitsOnly.length < 7 || digitsOnly.length > 15) {
      errs.phone = `Phone must have 7–15 digits (currently ${digitsOnly.length})`
    }

    // Party size
    const pCount = parseInt(values.people_count, 10)
    if (isNaN(pCount) || pCount < 1) {
      errs.people_count = 'Party size must be at least 1 person'
    } else if (pCount > 100) {
      errs.people_count = 'Party size cannot exceed 100 people'
    }

    // Latitude
    const lat = Number(values.latitude)
    if (values.latitude === '' || values.latitude === null || isNaN(lat)) {
      errs.latitude = 'Valid numerical latitude is required'
    } else if (lat < -90 || lat > 90) {
      errs.latitude = 'Latitude must be between -90.0° and +90.0°'
    }

    // Longitude
    const lon = Number(values.longitude)
    if (values.longitude === '' || values.longitude === null || isNaN(lon)) {
      errs.longitude = 'Valid numerical longitude is required'
    } else if (lon < -180 || lon > 180) {
      errs.longitude = 'Longitude must be between -180.0° and +180.0°'
    }

    // Message
    if (values.message && values.message.length > 500) {
      errs.message = 'Message must be under 500 characters'
    }

    return errs
  }

  const errors = validate(form)
  const isValid = Object.keys(errors).length === 0

  // Check distance from current district theater (~km)
  const latNum = Number(form.latitude)
  const lonNum = Number(form.longitude)
  const approxDistKm = (!isNaN(latNum) && !isNaN(lonNum))
    ? Math.round(Math.hypot((latNum - defaultLat) * 111, (lonNum - defaultLon) * 111 * Math.cos(defaultLat * Math.PI / 180)))
    : 0
  const isOutOfTheater = approxDistKm > 80

  const handleBlur = (field) => {
    setTouched((prev) => ({ ...prev, [field]: true }))
  }

  const handleApplyPreset = (preset) => {
    setForm((prev) => ({
      ...prev,
      name: preset.name,
      phone: preset.phone,
      people_count: preset.people_count,
      has_children: preset.has_children,
      has_elderly: preset.has_elderly,
      medical_emergency: preset.medical_emergency,
      message: preset.message,
      latitude: defaultLat,
      longitude: defaultLon,
    }))
    setTouched({})
    setServerError(null)
  }

  const handleSnapToTheater = () => {
    setForm((prev) => ({
      ...prev,
      latitude: Number(defaultLat.toFixed(4)),
      longitude: Number(defaultLon.toFixed(4)),
    }))
    setTouched((prev) => ({ ...prev, latitude: true, longitude: true }))
  }

  const handleSimulateSOS = async (e) => {
    e.preventDefault()
    setTouched({
      name: true,
      phone: true,
      people_count: true,
      latitude: true,
      longitude: true,
      message: true,
    })

    const currentErrors = validate(form)
    if (Object.keys(currentErrors).length > 0) {
      setServerError('Please fix the highlighted form validation errors before submitting.')
      return
    }

    setSubmitting(true)
    setServerError(null)

    try {
      let finalLat = Number(form.latitude)
      let finalLon = Number(form.longitude)

      if (form.addScatter) {
        // Small ~150m micro-scatter to prevent overlapping markers if multiple pins submitted
        finalLat += (Math.random() - 0.5) * 0.003
        finalLon += (Math.random() - 0.5) * 0.003
      }

      const payload = {
        name: form.name.trim(),
        phone: form.phone.trim(),
        people_count: parseInt(form.people_count, 10),
        has_children: Boolean(form.has_children),
        has_elderly: Boolean(form.has_elderly),
        medical_emergency: Boolean(form.medical_emergency),
        message: (form.message || '').trim(),
        latitude: Number(finalLat.toFixed(5)),
        longitude: Number(finalLon.toFixed(5)),
      }

      const newTicket = await submitSosTicket(payload)
      setShowForm(false)
      setForm({
        name: '',
        phone: '',
        people_count: 1,
        has_children: false,
        has_elderly: false,
        medical_emergency: false,
        message: '',
        latitude: defaultLat,
        longitude: defaultLon,
        addScatter: false,
      })
      setTouched({})

      // Focus map to newly triaged pin
      if (newTicket && newTicket.latitude && newTicket.longitude) {
        flyToTarget({
          lat: newTicket.latitude,
          lon: newTicket.longitude,
          zoom: 15.5,
          pitch: 52,
          bearing: -10,
        })
      }
    } catch (err) {
      console.error('[TIDALIS] SOS submission failed:', err)
      setServerError(err.message || 'Server rejected the distress signal. Check parameters.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleInspectTicket = (ticket) => {
    if (ticket.latitude && ticket.longitude) {
      flyToTarget({
        lat: ticket.latitude,
        lon: ticket.longitude,
        zoom: 15.5,
        pitch: 52,
        bearing: -15,
      })
    }
  }

  // ---------- Form View -----------------------------------------------------
  if (showForm) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '1px solid var(--border-soft)', paddingBottom: '8px' }}>
          <div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '12px', color: 'var(--text-hi)', fontWeight: 'bold' }}>
              SIMULATE INCOMING SOS DISTRESS BEACON
            </div>
            <div style={{ fontSize: '10px', color: 'var(--muted)' }}>
              Parameters are strictly validated against topographical bounds & contact rules
            </div>
          </div>
          <button
            type="button"
            className="btn"
            style={{ padding: '3px 8px', fontSize: '11px' }}
            onClick={() => {
              setShowForm(false)
              setServerError(null)
            }}
          >
            Cancel
          </button>
        </div>

        {/* Quick Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '10px', color: 'var(--muted)', fontFamily: 'var(--mono)' }}>PRESETS:</span>
          {PRESETS.map((p, idx) => (
            <button
              key={idx}
              type="button"
              className="copy-btn"
              onClick={() => handleApplyPreset(p)}
              style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', borderColor: 'var(--border)' }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Server or Global Error Banner */}
        {serverError && (
          <div style={{
            background: 'var(--red-dim)',
            border: '1px solid var(--red)',
            borderRadius: '6px',
            padding: '8px 12px',
            marginBottom: '10px',
            fontSize: '11px',
            color: 'var(--red)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <span>⚠️</span>
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSimulateSOS} style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', paddingRight: '6px' }} noValidate>
          {/* Name & Phone */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <div className="label" style={{ fontSize: '9px', marginBottom: '4px' }}>
                Contact Person / Family Name <span style={{ color: 'var(--red)' }}>*</span>
              </div>
              <input
                className="copilot-input"
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  background: 'var(--panel-2)',
                  border: '1px solid',
                  borderColor: touched.name && errors.name ? 'var(--red)' : 'var(--border)',
                  color: 'var(--text-hi)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                placeholder="e.g. Ramesh Naik"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                onBlur={() => handleBlur('name')}
              />
              {touched.name && errors.name && (
                <div style={{ color: 'var(--red)', fontSize: '10px', marginTop: '3px', fontFamily: 'var(--mono)' }}>
                  {errors.name}
                </div>
              )}
            </div>

            <div>
              <div className="label" style={{ fontSize: '9px', marginBottom: '4px' }}>
                Phone Number <span style={{ color: 'var(--red)' }}>*</span>
              </div>
              <input
                type="tel"
                className="copilot-input"
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  background: 'var(--panel-2)',
                  border: '1px solid',
                  borderColor: touched.phone && errors.phone ? 'var(--red)' : 'var(--border)',
                  color: 'var(--text-hi)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
                placeholder="e.g. +91 98231 12345"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                onBlur={() => handleBlur('phone')}
              />
              {touched.phone && errors.phone && (
                <div style={{ color: 'var(--red)', fontSize: '10px', marginTop: '3px', fontFamily: 'var(--mono)' }}>
                  {errors.phone}
                </div>
              )}
            </div>
          </div>

          {/* Coordinates */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span className="label" style={{ fontSize: '9px' }}>
                  GPS Latitude (-90 to +90) <span style={{ color: 'var(--red)' }}>*</span>
                </span>
              </div>
              <input
                type="number"
                step="0.0001"
                className="copilot-input"
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  background: 'var(--panel-2)',
                  border: '1px solid',
                  borderColor: touched.latitude && errors.latitude ? 'var(--red)' : 'var(--border)',
                  color: 'var(--text-hi)',
                  borderRadius: '6px',
                  fontFamily: 'var(--mono)',
                  fontSize: '12px',
                }}
                value={form.latitude}
                onChange={(e) => setForm({ ...form, latitude: e.target.value })}
                onBlur={() => handleBlur('latitude')}
              />
              {touched.latitude && errors.latitude && (
                <div style={{ color: 'var(--red)', fontSize: '10px', marginTop: '3px', fontFamily: 'var(--mono)' }}>
                  {errors.latitude}
                </div>
              )}
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span className="label" style={{ fontSize: '9px' }}>
                  GPS Longitude (-180 to +180) <span style={{ color: 'var(--red)' }}>*</span>
                </span>
              </div>
              <input
                type="number"
                step="0.0001"
                className="copilot-input"
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  background: 'var(--panel-2)',
                  border: '1px solid',
                  borderColor: touched.longitude && errors.longitude ? 'var(--red)' : 'var(--border)',
                  color: 'var(--text-hi)',
                  borderRadius: '6px',
                  fontFamily: 'var(--mono)',
                  fontSize: '12px',
                }}
                value={form.longitude}
                onChange={(e) => setForm({ ...form, longitude: e.target.value })}
                onBlur={() => handleBlur('longitude')}
              />
              {touched.longitude && errors.longitude && (
                <div style={{ color: 'var(--red)', fontSize: '10px', marginTop: '3px', fontFamily: 'var(--mono)' }}>
                  {errors.longitude}
                </div>
              )}
            </div>
          </div>

          {/* Theater bounds warning & Snap button */}
          {isOutOfTheater && (
            <div style={{
              background: 'rgba(251, 191, 36, 0.1)',
              border: '1px solid rgba(251, 191, 36, 0.35)',
              borderRadius: '6px',
              padding: '6px 10px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '11px',
              color: 'var(--amber)',
            }}>
              <span>Coordinates are ~{approxDistKm} km away from active operations theater.</span>
              <button
                type="button"
                className="copy-btn"
                onClick={handleSnapToTheater}
                style={{ fontSize: '10px', borderColor: 'var(--amber)', color: 'var(--amber)' }}
              >
                🎯 Snap to Theater Center
              </button>
            </div>
          )}

          {/* Party size & Vulnerabilities */}
          <div style={{
            display: 'flex',
            gap: '15px',
            alignItems: 'center',
            background: 'var(--panel-2)',
            padding: '10px',
            borderRadius: '6px',
            border: '1px solid var(--border-soft)',
            flexWrap: 'wrap',
          }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text)' }}>
              Party Size:
              <input
                type="number"
                min="1"
                max="100"
                style={{
                  width: '55px',
                  background: 'var(--bg)',
                  border: '1px solid',
                  borderColor: touched.people_count && errors.people_count ? 'var(--red)' : 'var(--border)',
                  color: 'var(--text-hi)',
                  padding: '3px 6px',
                  borderRadius: '4px',
                  fontFamily: 'var(--mono)',
                }}
                value={form.people_count}
                onChange={(e) => setForm({ ...form, people_count: e.target.value })}
                onBlur={() => handleBlur('people_count')}
              />
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={form.has_children}
                onChange={(e) => setForm({ ...form, has_children: e.target.checked })}
              />
              Children Present
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={form.has_elderly}
                onChange={(e) => setForm({ ...form, has_elderly: e.target.checked })}
              />
              Elderly Present
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--red)', cursor: 'pointer', fontWeight: 'bold' }}>
              <input
                type="checkbox"
                checked={form.medical_emergency}
                onChange={(e) => setForm({ ...form, medical_emergency: e.target.checked })}
              />
              Medical Emergency
            </label>
          </div>
          {touched.people_count && errors.people_count && (
            <div style={{ color: 'var(--red)', fontSize: '10px', fontFamily: 'var(--mono)', marginTop: '-4px' }}>
              {errors.people_count}
            </div>
          )}

          {/* Message / Situation */}
          <div>
            <div className="label" style={{ fontSize: '9px', marginBottom: '4px' }}>
              Situation Details / Landmarks (optional, max 500 chars)
            </div>
            <textarea
              style={{
                width: '100%',
                padding: '8px 10px',
                background: 'var(--panel-2)',
                border: '1px solid var(--border)',
                color: 'var(--text-hi)',
                borderRadius: '6px',
                minHeight: '55px',
                fontFamily: 'var(--sans)',
                fontSize: '12px',
              }}
              placeholder="e.g. Near church belfry, 2 children on rooftop, water depth ~1.2m..."
              value={form.message}
              onChange={(e) => setForm({ ...form, message: e.target.value })}
            />
          </div>

          {/* Micro-scatter option */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--muted)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={form.addScatter}
              onChange={(e) => setForm({ ...form, addScatter: e.target.checked })}
            />
            Add ±150m spatial scatter (prevents duplicate pins from stacking identically on map)
          </label>

          {/* Submit Action */}
          <button
            type="submit"
            className="btn"
            disabled={submitting || (Object.keys(touched).length > 0 && !isValid)}
            style={{
              marginTop: '4px',
              background: 'var(--red-dim)',
              borderColor: 'var(--red)',
              color: 'var(--red)',
              padding: '8px 14px',
              fontWeight: 'bold',
              fontFamily: 'var(--mono)',
              opacity: (Object.keys(touched).length > 0 && !isValid) || submitting ? 0.6 : 1,
              cursor: submitting ? 'wait' : 'pointer',
            }}
          >
            {submitting ? 'TRIAGING DISTRESS BEACON...' : '⚡ DROP SOS PIN (TRIAGE & DISPATCH)'}
          </button>
        </form>
      </div>
    )
  }

  // ---------- Tickets List View ---------------------------------------------
  const activeCount = sosTickets.filter((t) => t.status !== 'RESCUED').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '10px' }}>
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '13px', color: 'var(--text-hi)', fontWeight: 'bold' }}>
            Topographical SOS Triage & Rescue
          </div>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
            Active Distress Calls: <span style={{ color: activeCount > 0 ? 'var(--red)' : 'var(--green)', fontWeight: 'bold' }}>{activeCount}</span>
            {' · '}Total Triaged: {sosTickets.length}
          </div>
        </div>
        <button
          type="button"
          className="btn"
          onClick={() => {
            setShowForm(true)
            setForm((prev) => ({
              ...prev,
              latitude: Number(defaultLat.toFixed(4)),
              longitude: Number(defaultLon.toFixed(4)),
            }))
          }}
          style={{ background: 'var(--red-dim)', borderColor: 'var(--red)', color: 'var(--red)' }}
        >
          + Simulate Validated SOS
        </button>
      </div>

      {sosTickets.length === 0 ? (
        <div className="empty-state">NO ACTIVE DISTRESS SIGNALS RECORDED</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto' }}>
          {sosTickets.map((t) => {
            const isRescued = t.status === 'RESCUED'
            return (
              <div
                key={t.ticket_id}
                style={{
                  background: 'var(--panel-2)',
                  border: '1px solid',
                  borderColor: isRescued
                    ? 'var(--green)'
                    : t.urgency === 'CRITICAL'
                    ? 'rgba(251, 113, 133, 0.6)'
                    : t.urgency === 'HIGH'
                    ? 'rgba(251, 191, 36, 0.5)'
                    : 'var(--border-soft)',
                  borderRadius: '8px',
                  padding: '12px',
                  opacity: isRescued ? 0.65 : 1,
                  position: 'relative',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '12px', color: 'var(--text-hi)', fontWeight: 'bold' }}>
                      {t.ticket_id} • {t.name} ({t.people_count} {t.people_count === 1 ? 'person' : 'people'})
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
                      📞 {t.phone || 'No phone'}
                      {t.message ? ` — "${t.message}"` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <span style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--panel)', fontFamily: 'var(--mono)' }}>
                      {t.status}
                    </span>
                    <span className={`sev ${t.urgency}`} style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px' }}>
                      {t.urgency}
                    </span>
                  </div>
                </div>

                <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '8px', lineHeight: '1.4' }}>
                  <span style={{ color: t.water_margin_m < 0 ? 'var(--red)' : 'var(--text-hi)', fontFamily: 'var(--mono)' }}>
                    Elev: {t.elevation_m}m | Flood Depth: {t.predicted_flood_depth_m}m | Margin: {t.water_margin_m}m
                  </span>
                  {t.nearest_shelter && (
                    <span style={{ marginLeft: '10px', color: 'var(--muted)' }}>
                      Shelter: {t.nearest_shelter} ({t.distance_to_shelter_km}km)
                    </span>
                  )}
                  <br />
                  <span style={{ color: 'var(--text)' }}>{t.triage_reason}</span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px dashed var(--border)', paddingTop: '8px', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                    <span style={{ color: 'var(--muted)' }}>Rescue Vector:</span> {t.rescue_method?.replace(/_/g, ' ')}
                    <span style={{ marginLeft: '10px', color: 'var(--muted)' }}>ETA:</span> {t.eta_minutes}m
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="copy-btn"
                      style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
                      onClick={() => handleInspectTicket(t)}
                    >
                      🎯 LOCATE
                    </button>
                    {t.status === 'PENDING' && (
                      <button
                        type="button"
                        className="copy-btn"
                        style={{ borderColor: 'var(--accent)', color: 'var(--accent)', fontWeight: 'bold' }}
                        onClick={() => updateSosTicketStatus(t.ticket_id, 'DISPATCHED')}
                      >
                        DISPATCH CREW
                      </button>
                    )}
                    {t.status === 'DISPATCHED' && (
                      <button
                        type="button"
                        className="copy-btn"
                        style={{ borderColor: 'var(--amber)', color: 'var(--amber)', fontWeight: 'bold' }}
                        onClick={() => updateSosTicketStatus(t.ticket_id, 'RESCUED')}
                      >
                        MARK RESCUED
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
