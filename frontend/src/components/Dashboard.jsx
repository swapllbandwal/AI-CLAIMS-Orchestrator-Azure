import React, { useEffect, useState, useCallback } from 'react'
import { RefreshCw, FolderOpen } from 'lucide-react'
import { claimsAPI } from '../services/api'
import ClaimDetail from './ClaimDetail'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'needs_review', label: 'Needs Review' },
]

export default function Dashboard({ initialClaimId, clearInitialClaimId }) {
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(initialClaimId || null)
  const [filter, setFilter] = useState('all')

  const fetchClaims = useCallback(async () => {
    try {
      const data = await claimsAPI.listClaims()
      setClaims(data)
      setError(null)
    } catch (e) {
      setError('Failed to load claims')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchClaims()
    const t = setInterval(fetchClaims, 3000)
    return () => clearInterval(t)
  }, [fetchClaims])

  useEffect(() => {
    if (initialClaimId) {
      setSelected(initialClaimId)
      clearInitialClaimId && clearInitialClaimId()
    }
  }, [initialClaimId, clearInitialClaimId])

  if (selected) {
    return <ClaimDetail claimId={selected} onBack={() => setSelected(null)} />
  }

  const formatStatus = (s) =>
    s.split('_').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ')

  const filtered = claims.filter((c) => filter === 'all' || c.status === filter)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <FolderOpen size={24} color="#3b82f6" />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>All Claims</h2>
        </div>
        <button onClick={fetchClaims} className="btn btn-secondary" disabled={loading}>
          <RefreshCw size={18} /> Refresh
        </button>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`btn ${filter === f.key ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}
          >
            {f.label}
            {f.key !== 'all' && (
              <span style={{ marginLeft: 6, opacity: 0.85 }}>
                ({claims.filter((c) => c.status === f.key).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="loading">
          <div className="spinner" />
          <p>Loading claims…</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
            No claims to show. Submit your first claim from the Submit Claim tab.
          </p>
        </div>
      ) : (
        <div className="claims-grid">
          {filtered.map((c) => (
            <div key={c.claim_id} className={`claim-card ${c.status}`} onClick={() => setSelected(c.claim_id)}>
              <div className="claim-header">
                <span className="claim-id">{c.claim_id}</span>
                <span className={`status-badge status-${c.status}`}>{formatStatus(c.status)}</span>
              </div>
              <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>{c.claimant_name}</div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                {c.claim_type.toUpperCase()} · ${Number(c.claim_amount).toLocaleString()}
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${c.progress_percentage}%` }} />
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{c.current_step}</p>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
                Updated: {new Date(c.updated_at).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
