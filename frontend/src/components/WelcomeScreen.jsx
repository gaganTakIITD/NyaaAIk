import { IconGavel } from '../utils/icons.jsx'

// Gemini-style: clean greeting + suggestion cards in a 2-column grid
const SUGGESTIONS = [
  {
    title: 'BNS provisions on theft',
    query: 'What are the legal provisions for theft under Bharatiya Nyaya Sanhita 2023?',
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

export default function WelcomeScreen({ onSelect }) {
  return (
    <div className="welcome-screen">
      <div className="welcome-greeting">
        Hello, <span>Advocate</span>
      </div>
      <p className="welcome-sub">
        Ask any legal question. I'll search BNS provisions, find court precedents from Indian Kanoon, and generate a structured legal analysis using Llama 4 Maverick.
      </p>
      <div className="suggestion-grid">
        {SUGGESTIONS.map((s, i) => (
          <div
            key={i}
            className="suggestion-card"
            onClick={() => onSelect && onSelect(s.query)}
            role="button" tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && onSelect && onSelect(s.query)}
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
