import { useMemo } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import SourcesAccordion from './SourcesAccordion.jsx'
import { IconClock } from '../utils/icons.jsx'

marked.setOptions({ breaks: true, gfm: true })

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

function BotMessage({ msg }) {
  const html = useMemo(() => {
    try {
      const raw = marked.parse(msg.content || '')
      return DOMPurify.sanitize(raw, {
        ALLOWED_TAGS: ['p','br','strong','em','b','i','h1','h2','h3','h4','h5','h6','ul','ol','li','a','code','pre','blockquote','hr','table','thead','tbody','tr','th','td','span','div'],
        ALLOWED_ATTR: ['href','target','rel','class'],
      })
    } catch { return msg.content || '' }
  }, [msg.content])

  return (
    <div className="msg-row bot" role="article">
      {/* Avatar — clean gradient circle with gavel icon */}
      <div className="msg-avatar">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0d1117" strokeWidth="1.8" strokeLinecap="round">
          <path d="M14 3L21 10L10 21L3 14Z"/><line x1="10" y1="14" x2="21" y2="3"/>
          <line x1="3" y1="21" x2="8" y2="16"/>
        </svg>
      </div>

      <div className="msg-body">
        <div className="msg-bubble" dangerouslySetInnerHTML={{ __html: html }} />
        <SourcesAccordion
          lawSources={msg.lawSources}
          caseSources={msg.caseSources}
          disclaimer={msg.disclaimer}
        />
        <div className="msg-meta">
          <span>{formatTime(msg.timestamp)}</span>
          {msg.elapsed && (
            <span className="elapsed-tag">
              <IconClock size={10} />
              {msg.elapsed}s
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function UserMessage({ msg }) {
  return (
    <div className="msg-row user" role="article">
      <div className="msg-body">
        <div className="msg-bubble">{msg.content}</div>
        <div className="msg-meta">
          <span>{formatTime(msg.timestamp)}</span>
        </div>
      </div>
      {/* User avatar */}
      <div className="msg-avatar">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
      </div>
    </div>
  )
}

export default function MessageBubble({ msg }) {
  return msg.role === 'user' ? <UserMessage msg={msg} /> : <BotMessage msg={msg} />
}
