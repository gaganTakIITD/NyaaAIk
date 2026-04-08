import { IconGavel } from '../utils/icons.jsx'

// Clean text labels — Gemini-style, no emojis
const TOPICS = [
  { label: 'Theft & Robbery', query: 'What is the punishment for theft under BNS and what are landmark cases?' },
  { label: 'Murder / Homicide', query: 'What are the legal provisions for murder under BNS Section 101 and relevant precedents?' },
  { label: 'Bail Applications', query: 'What are the grounds for granting bail in non-bailable offences under BNSS?' },
  { label: 'Divorce Law', query: 'What are the grounds for divorce under Indian law for mutual consent?' },
  { label: 'Consumer Complaints', query: 'How do I file a consumer complaint in India for defective goods?' },
  { label: 'Property Dispute', query: 'What documents should I check before buying residential property in India?' },
  { label: 'Domestic Violence', query: 'What legal protections exist for victims of domestic violence in India?' },
  { label: 'FIR & Police Rights', query: 'What is the procedure to file an FIR and what are my rights when arrested?' },
  { label: 'Cyber Crime', query: 'What are the legal provisions for cybercrime and online fraud under BNS?' },
  { label: 'Cheque Bounce', query: 'What is the legal process for a cheque bounce case under NI Act Section 138?' },
]

export default function TopicsChips({ onSelect, disabled }) {
  return (
    <div className="topics-row" role="list" aria-label="Quick topics">
      {TOPICS.map((t, i) => (
        <button
          key={i}
          className="topic-chip"
          onClick={() => !disabled && onSelect(t.query)}
          disabled={disabled}
          title={t.query}
          role="listitem"
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
