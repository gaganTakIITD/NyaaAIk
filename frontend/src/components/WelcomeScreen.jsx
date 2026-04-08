import { IconGavel } from '../utils/icons.jsx'

const SUGGESTIONS = [
  {
    title: 'BNS provisions on theft',
    query: 'What are the legal provisions for theft under Bharatiya Nyaya Sanhita 2023 and relevant cases?',
  },
  {
    title: 'Bail in non-bailable offences',
    query: 'What are the grounds for granting bail in non-bailable offences under BNSS?',
  },
  {
    title: 'FIR filing procedure',
    query: 'What is the step-by-step procedure to file an FIR and my rights when arrested?',
  },
  {
    title: 'Consumer complaint process',
    query: 'How do I file a consumer complaint against a company under Indian consumer law?',
  },
]

// Suggestion cards pre-fill the input so user can edit before sending
export default function WelcomeScreen({ onPrefill }) {
  return (
    <div className="welcome-screen">
      <div className="welcome-greeting">
        Hello, <span>Advocate</span>
      </div>
      <p className="welcome-sub">
        Ask any legal question. I'll search BNS provisions, find court precedents from Indian Kanoon, and generate a structured legal analysis using Llama 4 Maverick.
      </p>
      <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: 16, marginTop: -16 }}>
        Click a suggestion to pre-fill — edit before sending. Paste a screenshot directly with Ctrl+V.
      </p>
      <div className="suggestion-grid">
        {SUGGESTIONS.map((s, i) => (
          <div
            key={i}
            className="suggestion-card"
            onClick={() => onPrefill && onPrefill(s.query)}
            role="button" tabIndex={0}
            aria-label={`Pre-fill: ${s.title}`}
            onKeyDown={e => e.key === 'Enter' && onPrefill && onPrefill(s.query)}
          >
            <div className="suggestion-card-title">
              <IconGavel size={14} />
              {s.title}
            </div>
            <div className="suggestion-card-query">{s.query}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
