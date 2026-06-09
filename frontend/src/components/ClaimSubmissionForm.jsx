import React, { useState } from 'react'
import { Upload, Camera, FileText, Send } from 'lucide-react'
import { claimsAPI } from '../services/api'

const initialForm = {
  policy_number: 'POL-AUTO-1001',
  claimant_name: '',
  claimant_email: '',
  incident_date: new Date().toISOString().slice(0, 10),
  claim_type: 'auto_collision',
  claim_amount: '',
  description: '',
  vehicle_make_model: '',
}

export default function ClaimSubmissionForm({ onSubmitted }) {
  const [form, setForm] = useState(initialForm)
  const [images, setImages] = useState([])
  const [docs, setDocs] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const update = (k, v) => setForm((prev) => ({ ...prev, [k]: v }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!form.claimant_name || !form.claimant_email || !form.claim_amount || !form.description) {
      setError('Please fill all required fields.')
      return
    }
    if (form.description.length < 20) {
      setError('Description must be at least 20 characters.')
      return
    }

    setSubmitting(true)
    try {
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => fd.append(k, v))
      images.forEach((f) => fd.append('images', f))
      docs.forEach((f) => fd.append('documents', f))

      const res = await claimsAPI.submitClaim(fd)
      onSubmitted(res.claim_id)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card">
      <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>
        Submit a New Auto Claim
      </h2>

      {error && <div className="alert alert-error">{error}</div>}

      <form onSubmit={onSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
          <div className="form-group">
            <label>Policy Number *</label>
            <input
              value={form.policy_number}
              onChange={(e) => update('policy_number', e.target.value)}
              placeholder="POL-AUTO-1001"
              required
            />
          </div>

          <div className="form-group">
            <label>Claim Type *</label>
            <select value={form.claim_type} onChange={(e) => update('claim_type', e.target.value)}>
              <option value="auto_collision">Auto — Collision</option>
              <option value="auto_theft">Auto — Theft</option>
              <option value="auto_vandalism">Auto — Vandalism</option>
              <option value="auto_weather">Auto — Weather</option>
            </select>
          </div>

          <div className="form-group">
            <label>Claimant Name *</label>
            <input value={form.claimant_name} onChange={(e) => update('claimant_name', e.target.value)} required />
          </div>

          <div className="form-group">
            <label>Claimant Email *</label>
            <input
              type="email"
              value={form.claimant_email}
              onChange={(e) => update('claimant_email', e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Incident Date *</label>
            <input
              type="date"
              value={form.incident_date}
              onChange={(e) => update('incident_date', e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Claim Amount (USD) *</label>
            <input
              type="number"
              min="1"
              step="0.01"
              value={form.claim_amount}
              onChange={(e) => update('claim_amount', e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ gridColumn: '1 / -1' }}>
            <label>Vehicle (make / model)</label>
            <input
              value={form.vehicle_make_model}
              onChange={(e) => update('vehicle_make_model', e.target.value)}
              placeholder="e.g. Maruti Suzuki Swift 2022"
            />
          </div>

          <div className="form-group" style={{ gridColumn: '1 / -1' }}>
            <label>Incident Description * (min. 20 chars)</label>
            <textarea
              value={form.description}
              onChange={(e) => update('description', e.target.value)}
              placeholder="Describe what happened, where and when…"
              required
            />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <FileDropZone
            label="Car damage photos"
            icon={<Camera size={20} />}
            accept="image/*"
            files={images}
            setFiles={setImages}
            hint="JPG / PNG of the damaged vehicle (multi-select supported)"
          />
          <FileDropZone
            label="Supporting documents"
            icon={<FileText size={20} />}
            accept="image/*,.pdf"
            files={docs}
            setFiles={setDocs}
            hint="Repair invoice, police report, receipts (images preferred for OCR)"
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={submitting} style={{ marginTop: '1rem' }}>
          {submitting ? (
            <>
              <div className="spinner" style={{ width: 20, height: 20 }} /> Submitting…
            </>
          ) : (
            <>
              <Send size={18} /> Submit Claim & Run AI Analysis
            </>
          )}
        </button>
      </form>
    </div>
  )
}

function FileDropZone({ label, icon, accept, files, setFiles, hint }) {
  const inputId = `file-${label.replace(/\s+/g, '-')}`
  const onChange = (e) => {
    const arr = Array.from(e.target.files || [])
    setFiles(arr)
  }
  return (
    <div className="form-group">
      <label>
        {icon} {label}
      </label>
      <label htmlFor={inputId} className="file-input-zone">
        <Upload size={20} />
        <div style={{ marginTop: '0.4rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          Click to choose files
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>{hint}</div>
        <input id={inputId} type="file" multiple accept={accept} onChange={onChange} />
      </label>
      {files.length > 0 && (
        <div className="file-list">
          {files.map((f, i) => (
            <span key={i} className="file-chip">{f.name}</span>
          ))}
        </div>
      )}
    </div>
  )
}
