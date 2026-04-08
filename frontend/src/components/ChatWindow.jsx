import { useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble.jsx'
import ThinkingIndicator from './ThinkingIndicator.jsx'
import WelcomeScreen from './WelcomeScreen.jsx'

export default function ChatWindow({ messages, isLoading, error, onClearError, onSuggestionSelect }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isLoading])

  const isEmpty = messages.length === 0

  return (
    <main className="chat-window" id="chatWindow" aria-label="Conversation" aria-live="polite">
      {isEmpty && !isLoading ? (
        <WelcomeScreen onSelect={onSuggestionSelect} />
      ) : (
        <>
          {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
          {isLoading && <ThinkingIndicator />}
          {error && (
            <div
              role="alert"
              style={{
                margin: '0 20px',
                padding: '12px 16px',
                background: 'var(--error-dim)',
                border: '1px solid rgba(242,139,130,0.2)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--error)',
                fontSize: '0.84rem',
                display: 'flex', alignItems: 'center', gap: 12,
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span style={{ flex: 1 }}>{error}</span>
              <button
                onClick={onClearError}
                style={{
                  background: 'transparent', border: 'none',
                  color: 'var(--error)', cursor: 'pointer',
                  fontSize: '0.8rem', fontFamily: 'inherit',
                  padding: '2px 6px', borderRadius: 4, transition: 'background 0.15s',
                }}
              >Dismiss</button>
            </div>
          )}
        </>
      )}
      <div ref={bottomRef} aria-hidden="true" />
    </main>
  )
}
