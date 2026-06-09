import React, { useEffect, useState, useCallback } from 'react'
import {
  ArrowLeft, CheckCircle, XCircle, AlertCircle, Clock,
  Camera, FileText, ShieldCheck, ShieldAlert, Gavel,
  Award, FileImage,
} from 'lucide-react'
import { claimsAPI } from '../services/api'
import DamageVisualization from './DamageVisualization'

const POLL_MS = 3000

export default function ClaimDetail({ claimId, onBack }) {
  const [claim, setClaim] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeImageIdx, setActiveImageIdx] = useState(0)

  const fetchClaim = useCallback(async () => {
    try {
      const data = await claimsAPI.getClaim(claimId)
      setClaim(data)
      setError(null)
    } catch (e) {
      setError('Failed to load claim')
    } finally {
      setLoading(false)
    }
  }, [claimId])

  useEffect(() => {
    fetchClaim()
    const t = setInterval(() => {
      // Stop polling once final
      if (claim && ['approved', 'rejected', 'needs_info', 'needs_review', 'escalated'].includes(claim.status)) return
      fetchClaim()
    }, POLL_MS)
    return () => clearInterval(t)
  }, [fetchClaim, claim])

  if (loading) return <div className="loading"><div className="spinner" /><p>Loading claim…</p></div>
  if (!claim) return (
    <div className="card">
      <div className="alert alert-error">{error || 'Claim not found'}</div>
      <button onClick={onBack} className="btn btn-secondary"><ArrowLeft size={18} /> Back</button>
    </div>
  )

  const analysis = claim.analysis
  const damageMeta = analysis?.damage_result?.metadata || {}
  const perImage = damageMeta.per_image || []
  const activeImage = perImage[activeImageIdx]
  const activeImageName = activeImage?.filename || claim.image_files?.[0]
  const activeImageUrl = activeImageName ? claimsAPI.imageUrl(claimId, activeImageName) : null
  // Filter overlay regions to the currently-displayed image
  const overlayRegions = (damageMeta.damage_regions || []).filter(
    (r) => !r.image || r.image === activeImageName
  )

  return (
    <div>
      <button onClick={onBack} className="btn btn-secondary" style={{ marginBottom: '1rem' }}>
        <ArrowLeft size={18} /> Back to Dashboard
      </button>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>{claim.claim_id}</h2>
          <span className={`status-badge status-${claim.status}`}>{formatStatus(claim.status)}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.6rem', marginBottom: '1rem' }}>
          <Info label="Claimant" value={claim.submission.claimant_name} />
          <Info label="Email" value={claim.submission.claimant_email} />
          <Info label="Policy" value={claim.submission.policy_number} />
          <Info label="Type" value={claim.submission.claim_type.toUpperCase()} />
          <Info label="Amount" value={`$${Number(claim.submission.claim_amount).toLocaleString()}`} />
          <Info label="Incident date" value={claim.submission.incident_date} />
          <Info label="Vehicle" value={claim.submission.vehicle_make_model || '—'} />
        </div>

        <div className="progress-bar"><div className="progress-fill" style={{ width: `${claim.progress_percentage}%` }} /></div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
          {claim.current_step} — {claim.progress_percentage}% complete
        </p>
      </div>

      {/* CV showcase / damage overlay */}
      {claim.image_files?.length > 0 && (
        <div className="detail-layout">
          <div className="card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Camera size={20} color="#3b82f6" /> Damage detection (Azure Computer Vision)
            </h3>

            {perImage.length > 1 && (
              <div className="image-thumbs">
                {perImage.map((img, i) => (
                  <img
                    key={img.filename}
                    src={claimsAPI.imageUrl(claimId, img.filename)}
                    alt={img.filename}
                    className={`image-thumb ${i === activeImageIdx ? 'active' : ''}`}
                    onClick={() => setActiveImageIdx(i)}
                  />
                ))}
              </div>
            )}

            {activeImageUrl ? (
              <DamageVisualization imageUrl={activeImageUrl} regions={overlayRegions} />
            ) : (
              <p style={{ color: 'var(--text-secondary)' }}>Waiting for CV analysis…</p>
            )}

            {damageMeta.severity && damageMeta.severity !== 'UNKNOWN' && (
              <p style={{ marginTop: '0.5rem' }}>
                Severity: <strong>{damageMeta.severity}</strong>
                {damageMeta.brand && (
                  <span className="brand-chip" style={{ marginLeft: '0.6rem' }}>
                    <Award size={14} /> {damageMeta.brand}
                  </span>
                )}
              </p>
            )}
          </div>

          <CVShowcase activeImage={activeImage} documentMeta={analysis?.document_result?.metadata} />
        </div>
      )}

      {/* Agent Results */}
      {analysis && (
        <div className="card">
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '1rem' }}>AI Pipeline Results</h3>
          <div className="agent-results">
            <AgentCard icon={<ShieldCheck size={20} color="#10b981" />} result={analysis.validation_result} confLabel="Confidence" />
            <AgentCard icon={<Camera size={20} color="#3b82f6" />} result={analysis.damage_result} confLabel="Confidence" />
            <AgentCard icon={<FileText size={20} color="#3b82f6" />} result={analysis.document_result} confLabel="Confidence" />
            <AgentCard icon={<ShieldAlert size={20} color="#ef4444" />} result={analysis.fraud_result} confLabel="Risk Score" />
            <AgentCard icon={<ShieldCheck size={20} color="#10b981" />} result={analysis.policy_result} confLabel="Confidence" />
            <AgentCard icon={<Gavel size={20} color="#111827" />} result={analysis.final_decision} confLabel="Confidence" emphasis />
          </div>
          {analysis.processing_time && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--bg-color)', borderRadius: 8, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Pipeline completed in {analysis.processing_time.toFixed(2)} seconds.
            </div>
          )}
        </div>
      )}

      {/* Human-in-loop review */}
      {claim.status === 'needs_review' && !claim.human_review && (
        <ReviewPanel claimId={claim.claim_id} onSubmitted={fetchClaim} />
      )}
      {claim.human_review && (
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.5rem' }}>Human review recorded</h3>
          <p><strong>Action:</strong> {claim.human_review.action.toUpperCase()}</p>
          <p><strong>By:</strong> {claim.human_review.reviewer_id}</p>
          <p style={{ marginTop: '0.5rem' }}><strong>Note:</strong> {claim.human_review.reviewer_note}</p>
        </div>
      )}
    </div>
  )
}

function formatStatus(s) {
  return s.split('_').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ')
}

function Info({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.04em' }}>{label}</div>
      <div style={{ fontWeight: 600 }}>{value}</div>
    </div>
  )
}

function statusIcon(status) {
  const map = {
    passed: <CheckCircle size={18} color="#10b981" />,
    approved: <CheckCircle size={18} color="#10b981" />,
    failed: <XCircle size={18} color="#ef4444" />,
    rejected: <XCircle size={18} color="#ef4444" />,
    warning: <AlertCircle size={18} color="#f59e0b" />,
    needs_info: <AlertCircle size={18} color="#f59e0b" />,
    needs_review: <AlertCircle size={18} color="#f59e0b" />,
  }
  return map[status] || <Clock size={18} color="#6b7280" />
}

function AgentCard({ result, confLabel, emphasis, icon }) {
  if (!result) {
    return (
      <div className="agent-card">
        <div className="agent-header"><span className="agent-name"><Clock size={18} /> Pending…</span></div>
      </div>
    )
  }
  return (
    <div className={`agent-card ${result.status}`} style={emphasis ? { borderLeftWidth: 8 } : null}>
      <div className="agent-header">
        <span className="agent-name">{icon || statusIcon(result.status)} {result.agent_name}</span>
        <span className="confidence-score">{confLabel}: {(result.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="findings">{result.findings}</div>
      {result.recommendations?.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <strong style={{ fontSize: '0.85rem' }}>Recommendations:</strong>
          <ul style={{ margin: '0.3rem 0 0 1.2rem', fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            {result.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function CVShowcase({ activeImage, documentMeta }) {
  if (!activeImage && !documentMeta) {
    return (
      <div className="cv-showcase">
        <h3><FileImage size={18} /> Azure CV Showcase</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
          Raw Azure Computer Vision outputs will appear here once the pipeline runs.
        </p>
      </div>
    )
  }

  const ocrSection = (documentMeta?.per_document || []).filter((d) => d.ocr_text)

  return (
    <div className="cv-showcase">
      <h3><FileImage size={18} /> Azure CV Showcase</h3>

      {activeImage?.caption && (
        <div className="cv-section">
          <div className="cv-label">Caption (Image Analysis 4.0)</div>
          <div>"{activeImage.caption.text}" <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
            ({(activeImage.caption.confidence * 100).toFixed(0)}%)
          </span></div>
        </div>
      )}

      {activeImage?.tags?.length > 0 && (
        <div className="cv-section">
          <div className="cv-label">Tags</div>
          {activeImage.tags.slice(0, 10).map((t) => (
            <span key={t.name} className="tag-chip">{t.name} {(t.confidence * 100).toFixed(0)}%</span>
          ))}
        </div>
      )}

      {activeImage?.dense_captions?.length > 0 && (
        <div className="cv-section">
          <div className="cv-label">Dense captions (regions)</div>
          {activeImage.dense_captions.slice(0, 6).map((dc, i) => (
            <div key={i} className="dense-caption-row">
              "{dc.text}" <span style={{ color: 'var(--text-secondary)' }}>({(dc.confidence * 100).toFixed(0)}%)</span>
            </div>
          ))}
        </div>
      )}

      {activeImage?.brand && (
        <div className="cv-section">
          <div className="cv-label">Brand (Vision v3.2)</div>
          <span className="brand-chip"><Award size={14} /> {activeImage.brand}</span>
        </div>
      )}

      {ocrSection.length > 0 && (
        <div className="cv-section">
          <div className="cv-label">OCR / Read API (supporting documents)</div>
          {ocrSection.map((d, i) => (
            <div key={i} style={{ marginBottom: '0.6rem' }}>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                {d.filename}
              </div>
              <div className="ocr-text">{d.ocr_text.slice(0, 600)}{d.ocr_text.length > 600 ? '…' : ''}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ReviewPanel({ claimId, onSubmitted }) {
  const [action, setAction] = useState(null)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async () => {
    if (!action) { setErr('Choose an action'); return }
    if (note.trim().length < 3) { setErr('Reviewer note is required (min 3 chars)'); return }
    setSubmitting(true)
    setErr(null)
    try {
      await claimsAPI.submitReview(claimId, { action, reviewer_note: note, reviewer_id: 'demo-analyst' })
      onSubmitted && onSubmitted()
    } catch (e) {
      setErr(e.response?.data?.detail || e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card review-panel">
      <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '0.4rem' }}>
        Human-in-the-loop review required
      </h3>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.9rem' }}>
        The AI pipeline could not make a fully confident decision. Please review the
        evidence above and pick an action.
      </p>

      <div className="action-grid">
        <ActionBtn cur={action} set={setAction} k="approve"      label="Approve"     icon={<CheckCircle size={16} />} />
        <ActionBtn cur={action} set={setAction} k="reject"       label="Reject"      icon={<XCircle size={16} />} />
        <ActionBtn cur={action} set={setAction} k="request_info" label="Request Info" icon={<AlertCircle size={16} />} />
        <ActionBtn cur={action} set={setAction} k="escalate"     label="Escalate"    icon={<ShieldAlert size={16} />} />
      </div>

      <div className="form-group">
        <label>Reviewer note *</label>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3}
          placeholder="Explain your decision (will be saved to the claim audit log)" />
      </div>

      {err && <div className="alert alert-error">{err}</div>}

      <button onClick={submit} className="btn btn-primary" disabled={submitting || !action}>
        {submitting ? 'Submitting…' : 'Submit decision'}
      </button>
    </div>
  )
}

function ActionBtn({ cur, set, k, label, icon }) {
  const active = cur === k
  return (
    <button
      onClick={() => set(k)}
      className={`btn ${active ? 'btn-primary' : 'btn-secondary'}`}
    >
      {icon} {label}
    </button>
  )
}
