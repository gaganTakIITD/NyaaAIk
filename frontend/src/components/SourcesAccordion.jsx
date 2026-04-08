import { useState } from 'react'

export default function SourcesAccordion({ lawSources, caseSources, disclaimer }) {
  const [open, setOpen] = useState(false)
  const hasLaw = lawSources && lawSources.length > 0
  const hasCases = caseSources && caseSources.length > 0
  if (!hasLaw && !hasCases) return null

  const total = (lawSources?.length || 0) + (caseSources?.length || 0)

  return (
    <div>
      <button
        className="sources-toggle"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        {total} source{total !== 1 ? 's' : ''} cited
        <em className={`sources-arrow${open ? ' open' : ''}`}>▶</em>
      </button>

      {open && (
        <div className="sources-content">
          <div className="sources-inner">
            {hasLaw && (
              <>
                <div className="source-section-title">
                  <span>📚</span> Law Sections
                </div>
                {lawSources.map((s, i) => (
                  <div key={i} className="source-item">
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>{s}</span>
                  </div>
                ))}
              </>
            )}
            {hasCases && (
              <>
                <div className="source-section-title">
                  <span>⚖️</span> Court Precedents
                </div>
                {caseSources.map((c, i) => (
                  <div key={i} className="source-item">
                    {c.url ? (
                      <a href={c.url} target="_blank" rel="noopener noreferrer">
                        {c.title}
                        {c.court && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>· {c.court}</span>}
                        {c.date && <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>({c.date.slice(0, 4)})</span>}
                      </a>
                    ) : (
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>
                        {c.title}
                        {c.court && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>· {c.court}</span>}
                      </span>
                    )}
                  </div>
                ))}
              </>
            )}
            {disclaimer && (
              <div className="disclaimer">{disclaimer}</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
