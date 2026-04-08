import { IconGavel } from '../utils/icons.jsx'

const ADVOCATE_SUGGESTIONS = [
  {
    title: 'BNS Section Analysis',
    query: 'Analyze the statutory provisions for theft under BNS Section 303-305 with ratio decidendi from landmark precedents.',
  },
  {
    title: 'Bail in Non-Bailable Offences',
    query: 'What are the grounds for granting bail in non-bailable offences under BNSS Section 480 and relevant Supreme Court precedents?',
  },
  {
    title: 'Cognizance & FIR',
    query: 'Explain the legal procedure for filing an FIR, cognizance under BNSS, and rights of the accused upon arrest.',
  },
  {
    title: 'Evidence Admissibility',
    query: 'Under the Bharatiya Sakshya Adhiniyam, what are the provisions for admissibility of digital and electronic evidence?',
  },
]

const CITIZEN_SUGGESTIONS = [
  {
    title: 'Someone stole from me',
    query: 'Someone stole my phone. What should I do? How do I file a complaint and what will happen next?',
  },
  {
    title: 'Police arrested my family member',
    query: 'The police arrested my brother. What are his rights? Can we get him released on bail and how?',
  },
  {
    title: 'File a consumer complaint',
    query: 'A company cheated me and refused to refund my money. How do I file a complaint against them?',
  },
  {
    title: 'Property dispute with neighbour',
    query: 'My neighbour is encroaching on my land. What can I do legally to stop them?',
  },
]

export default function WelcomeScreen({ onPrefill, persona }) {
  const isCitizen = persona === 'citizen'
  const suggestions = isCitizen ? CITIZEN_SUGGESTIONS : ADVOCATE_SUGGESTIONS

  return (
    <div className="welcome-screen">
      <div className="welcome-greeting">
        {isCitizen ? (
          <>Hello, <span style={{ color: 'var(--accent)' }}>how can I help you today?</span></>
        ) : (
          <>Good day, <span style={{ color: 'var(--accent)' }}>Advocate</span></>
        )}
      </div>
      <p className="welcome-sub">
        {isCitizen
          ? "Tell me your legal problem in simple words. I'll explain the law clearly and tell you exactly what to do next."
          : "Ask any legal question. I'll search BNS provisions, find court precedents from Indian Kanoon, and generate a structured legal brief using Llama 4 Maverick."
        }
      </p>
      <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: 16, marginTop: -16 }}>
        Click a suggestion to pre-fill — edit before sending. Paste a screenshot directly with Ctrl+V.
      </p>
      <div className="suggestion-grid">
        {suggestions.map((s, i) => (
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
