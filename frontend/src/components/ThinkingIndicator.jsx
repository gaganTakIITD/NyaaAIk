import { useState } from 'react'
import { IconClock, IconFile } from '../utils/icons.jsx'

export default function ThinkingIndicator() {
  const [step] = useState(0)
  const steps = [
    'Searching BNS law sections',
    'Querying Indian Kanoon precedents',
    'Analyzing with Maverick',
    'Structuring response',
  ]
  const [currentStep, setCurrentStep] = useState(0)

  // rotate steps
  useState(() => {
    const t = setInterval(() => setCurrentStep(p => (p + 1) % steps.length), 1800)
    return () => clearInterval(t)
  })

  return (
    <div className="thinking-row" role="status" aria-live="polite">
      <div
        className="msg-avatar"
        style={{ background: 'linear-gradient(135deg, #a8c7fa 0%, #c2a8fa 100%)', borderRadius: '50%' }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0d1117" strokeWidth="1.8" strokeLinecap="round">
          <path d="M14 3L21 10L10 21L3 14Z"/><line x1="10" y1="14" x2="21" y2="3"/>
          <line x1="3" y1="21" x2="8" y2="16"/>
        </svg>
      </div>
      <div className="thinking-content">
        <div className="thinking-dots" aria-hidden="true">
          <span /><span /><span />
        </div>
        <div>
          <div className="thinking-label">Researching your query</div>
          <div className="thinking-step">{steps[currentStep]}</div>
        </div>
      </div>
    </div>
  )
}
