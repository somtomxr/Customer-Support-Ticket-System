import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSimilarTickets } from '../services/similarityService'

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Map a cosine similarity score [0, 1] to a visual tier.
 * Returns { label, barColor, badgeClass, bgClass }
 */
function scoreStyle(score) {
  if (score >= 0.85) return {
    label: 'Very High',
    barColor: '#22c55e',       // green-500
    badgeClass: 'similar-badge similar-badge--high',
    bgClass: 'similar-card--high',
  }
  if (score >= 0.70) return {
    label: 'High',
    barColor: '#84cc16',       // lime-500
    badgeClass: 'similar-badge similar-badge--medium-high',
    bgClass: 'similar-card--medium-high',
  }
  if (score >= 0.55) return {
    label: 'Medium',
    barColor: '#f59e0b',       // amber-500
    badgeClass: 'similar-badge similar-badge--medium',
    bgClass: 'similar-card--medium',
  }
  return {
    label: 'Low',
    barColor: '#94a3b8',       // slate-400
    badgeClass: 'similar-badge similar-badge--low',
    bgClass: 'similar-card--low',
  }
}

const STATUS_COLORS = {
  open: '#3b82f6',
  in_progress: '#f59e0b',
  resolved: '#22c55e',
}

// ── Skeleton loader ────────────────────────────────────────────────────────────

function SimilarSkeleton() {
  return (
    <div className="similar-skeleton-list">
      {[1, 2, 3].map((i) => (
        <div key={i} className="similar-skeleton-item">
          <div className="similar-skeleton-line similar-skeleton-line--title" />
          <div className="similar-skeleton-line similar-skeleton-line--meta" />
          <div className="similar-skeleton-bar-bg">
            <div className="similar-skeleton-bar" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function SimilarTickets({ ticketId }) {
  const navigate = useNavigate()
  const [data, setData] = useState(null)   // { results, method }
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(true)

  const fetch = useCallback(async () => {
    if (!ticketId) return
    setLoading(true)
    setError(null)
    try {
      const res = await getSimilarTickets(ticketId, 5)
      setData(res)
    } catch (err) {
      setError('Could not load similar tickets.')
    } finally {
      setLoading(false)
    }
  }, [ticketId])

  useEffect(() => { fetch() }, [fetch])

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      <style>{STYLES}</style>

      <div className="similar-panel">
        {/* Header */}
        <button
          className="similar-header"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          id="similar-tickets-toggle"
        >
          <span className="similar-header__icon">🔍</span>
          <span className="similar-header__title">Similar Tickets</span>
          {data?.method === 'semantic' && (
            <span className="similar-header__method-badge">ML · cosine sim</span>
          )}
          <span className={`similar-header__chevron ${expanded ? 'similar-header__chevron--open' : ''}`}>
            ▾
          </span>
        </button>

        {/* Body */}
        {expanded && (
          <div className="similar-body">
            {loading && <SimilarSkeleton />}

            {!loading && error && (
              <div className="similar-empty">
                <span className="similar-empty__icon">⚠️</span>
                <p>{error}</p>
                <button className="similar-retry" onClick={fetch} id="similar-retry-btn">Retry</button>
              </div>
            )}

            {!loading && !error && data?.method === 'unavailable' && (
              <div className="similar-empty">
                <span className="similar-empty__icon">🤖</span>
                <p className="similar-empty__title">ML engine offline</p>
                <p className="similar-empty__sub">Install <code>sentence-transformers</code> and restart the server.</p>
              </div>
            )}

            {!loading && !error && data?.method === 'semantic' && data.results.length === 0 && (
              <div className="similar-empty">
                <span className="similar-empty__icon">🎯</span>
                <p>No similar tickets found.</p>
                <p className="similar-empty__sub">This ticket seems unique!</p>
              </div>
            )}

            {!loading && !error && data?.results?.length > 0 && (
              <ul className="similar-list">

                {/* ── Suggested Priority Banner ── */}
                {data.suggested_priority && (
                  <li>
                    <div className={`similar-priority-banner similar-priority-banner--${data.suggested_priority}`}>
                      <span className="similar-priority-banner__label">🤖 Suggested Priority</span>
                      <span className={`similar-priority-banner__pill similar-priority-pill--${data.suggested_priority}`}>
                        {data.suggested_priority.toUpperCase()}
                      </span>
                      <span className="similar-priority-banner__conf">
                        {Math.round(data.priority_confidence * 100)}% confidence
                      </span>
                    </div>
                  </li>
                )}
                {data.results.map((ticket, idx) => {
                  const style = scoreStyle(ticket.similarity_score)
                  const pct = Math.round(ticket.similarity_score * 100)
                  return (
                    <li key={ticket.id}>
                      <button
                        id={`similar-ticket-${ticket.id}`}
                        className={`similar-card ${style.bgClass}`}
                        onClick={() => navigate(`/tickets/${ticket.id}`)}
                      >
                        {/* Rank + title row */}
                        <div className="similar-card__top">
                          <span className="similar-card__rank">#{idx + 1}</span>
                          <span className="similar-card__title">{ticket.title}</span>
                        </div>

                        {/* Meta row */}
                        <div className="similar-card__meta">
                          <span
                            className="similar-card__status-dot"
                            style={{ background: STATUS_COLORS[ticket.status] ?? '#94a3b8' }}
                          />
                          <span className="similar-card__status">
                            {ticket.status.replace('_', ' ')}
                          </span>
                          <span className="similar-card__sep">·</span>
                          <span className="similar-card__priority">{ticket.priority}</span>
                          {ticket.customer_name && (
                            <>
                              <span className="similar-card__sep">·</span>
                              <span className="similar-card__customer">{ticket.customer_name}</span>
                            </>
                          )}
                        </div>

                        {/* Score bar */}
                        <div className="similar-card__score-row">
                          <div className="similar-score-bar-bg">
                            <div
                              className="similar-score-bar-fill"
                              style={{
                                width: `${pct}%`,
                                background: style.barColor,
                              }}
                            />
                          </div>
                          <span className={style.badgeClass}>{pct}%</span>
                          <span className="similar-card__score-label">{style.label}</span>
                        </div>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}

            {/* Footer */}
            {!loading && data?.method === 'semantic' && data.results.length > 0 && (
              <div className="similar-footer">
                Powered by <strong>all-MiniLM-L6-v2</strong> · 384-dim embeddings
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}

// ── Scoped CSS-in-JS styles ────────────────────────────────────────────────────

const STYLES = `
  .similar-panel {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.07);
    overflow: hidden;
  }

  /* Header */
  .similar-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 14px 16px;
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border: none;
    cursor: pointer;
    text-align: left;
    border-bottom: 1px solid #e0f2fe;
    transition: background .15s;
  }
  .similar-header:hover { background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%); }
  .similar-header__icon { font-size: 16px; }
  .similar-header__title {
    font-size: 13px;
    font-weight: 700;
    color: #0c4a6e;
    flex: 1;
  }
  .similar-header__method-badge {
    font-size: 10px;
    font-weight: 600;
    color: #0369a1;
    background: #e0f2fe;
    border: 1px solid #bae6fd;
    padding: 2px 7px;
    border-radius: 99px;
    letter-spacing: .3px;
  }
  .similar-header__chevron {
    font-size: 14px;
    color: #0369a1;
    transition: transform .2s;
    display: inline-block;
  }
  .similar-header__chevron--open { transform: rotate(180deg); }

  /* Body */
  .similar-body { padding: 10px 10px 6px; }

  /* Result list — full height of its column; column itself is max-h capped */
  .similar-list {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 6px;
    scrollbar-width: thin;
    scrollbar-color: #cbd5e1 transparent;
  }

  /* Card */
  .similar-card {
    width: 100%;
    text-align: left;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 9px;
    padding: 10px 12px;
    cursor: pointer;
    transition: transform .15s, box-shadow .15s, border-color .15s;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .similar-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,.1);
    border-color: #93c5fd;
  }
  .similar-card--high     { border-left: 3px solid #22c55e; }
  .similar-card--medium-high { border-left: 3px solid #84cc16; }
  .similar-card--medium   { border-left: 3px solid #f59e0b; }
  .similar-card--low      { border-left: 3px solid #94a3b8; }

  .similar-card__top { display: flex; align-items: flex-start; gap: 6px; }
  .similar-card__rank {
    font-size: 10px;
    font-weight: 700;
    color: #94a3b8;
    min-width: 16px;
    padding-top: 2px;
  }
  .similar-card__title {
    font-size: 12px;
    font-weight: 600;
    color: #1e293b;
    line-height: 1.4;
    flex: 1;
  }

  .similar-card__meta {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: #64748b;
    flex-wrap: wrap;
  }
  .similar-card__status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .similar-card__status { text-transform: capitalize; }
  .similar-card__sep { color: #cbd5e1; }
  .similar-card__priority { text-transform: capitalize; }
  .similar-card__customer { color: #94a3b8; }

  .similar-card__score-row { display: flex; align-items: center; gap: 6px; }
  .similar-score-bar-bg {
    flex: 1;
    height: 4px;
    background: #e2e8f0;
    border-radius: 99px;
    overflow: hidden;
  }
  .similar-score-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width .4s ease;
  }
  .similar-card__score-label { font-size: 10px; color: #94a3b8; }

  /* Score badges */
  .similar-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 99px;
    white-space: nowrap;
  }
  .similar-badge--high       { background: #dcfce7; color: #15803d; }
  .similar-badge--medium-high{ background: #ecfccb; color: #4d7c0f; }
  .similar-badge--medium     { background: #fef9c3; color: #a16207; }
  .similar-badge--low        { background: #f1f5f9; color: #64748b; }

  /* Empty state */
  .similar-empty {
    text-align: center;
    padding: 24px 12px;
    color: #64748b;
    font-size: 12px;
  }
  .similar-empty__icon { font-size: 28px; display: block; margin-bottom: 8px; }
  .similar-empty__title { font-weight: 600; color: #374151; margin-bottom: 4px; }
  .similar-empty__sub { color: #94a3b8; font-size: 11px; }
  .similar-empty code {
    background: #f1f5f9;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 11px;
    color: #0369a1;
  }

  /* Priority suggestion banner */
  .similar-priority-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px dashed;
    margin-bottom: 2px;
    flex-wrap: wrap;
  }
  .similar-priority-banner--urgent { background: #fff1f2; border-color: #fca5a5; }
  .similar-priority-banner--high   { background: #fff7ed; border-color: #fdba74; }
  .similar-priority-banner--medium { background: #fefce8; border-color: #fde047; }
  .similar-priority-banner--low    { background: #f0fdf4; border-color: #86efac; }
  .similar-priority-banner__label  { font-size: 11px; color: #64748b; flex: 1; min-width: 110px; }
  .similar-priority-banner__conf   { font-size: 10px; color: #94a3b8; }

  .similar-priority-pill--urgent { background:#fee2e2; color:#b91c1c; font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; }
  .similar-priority-pill--high   { background:#ffedd5; color:#c2410c; font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; }
  .similar-priority-pill--medium { background:#fef9c3; color:#a16207; font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; }
  .similar-priority-pill--low    { background:#dcfce7; color:#15803d; font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; }
  .similar-retry {
    margin-top: 10px;
    font-size: 11px;
    color: #3b82f6;
    background: none;
    border: 1px solid #93c5fd;
    border-radius: 6px;
    padding: 4px 12px;
    cursor: pointer;
    transition: background .15s;
  }
  .similar-retry:hover { background: #eff6ff; }

  /* Footer */
  .similar-footer {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #f1f5f9;
    font-size: 10px;
    color: #94a3b8;
    text-align: center;
  }
  .similar-footer strong { color: #64748b; }

  /* Skeleton */
  .similar-skeleton-list { display: flex; flex-direction: column; gap: 8px; }
  .similar-skeleton-item {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 9px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .similar-skeleton-line {
    background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s infinite;
    border-radius: 4px;
  }
  .similar-skeleton-line--title  { height: 11px; width: 85%; }
  .similar-skeleton-line--meta   { height: 9px;  width: 55%; }
  .similar-skeleton-bar-bg       { height: 4px; background: #e2e8f0; border-radius: 99px; overflow: hidden; }
  .similar-skeleton-bar {
    width: 60%;
    height: 100%;
    background: linear-gradient(90deg, #e2e8f0 25%, #cbd5e1 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s infinite;
    border-radius: 99px;
  }
  @keyframes shimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
`
