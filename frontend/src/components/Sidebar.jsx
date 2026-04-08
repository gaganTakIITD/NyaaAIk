import { IconScale, IconPlus, IconChat, IconTrash, IconFile, IconImage } from '../utils/icons.jsx'

function formatDate(ts) {
  const d = new Date(ts), now = new Date(), diff = now - d
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function isImageDoc(filename = '') {
  return /\.(png|jpg|jpeg|webp|gif)$/i.test(filename)
}

export default function Sidebar({
  open, conversations, activeId,
  onSelect, onNewChat, onDelete,
  documents, activeDocIds, onRemoveDoc, onToggleDoc,
}) {
  return (
    <aside className={`sidebar${open ? '' : ' collapsed'}`} aria-label="Sidebar">
      <div className="sidebar-header">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <IconScale size={16} color="#0d1117" />
          </div>
          <span className="sidebar-logo-text">NyaaAIk</span>
        </div>

        {/* New Chat */}
        <button className="new-chat-btn" onClick={onNewChat} id="newChatBtn" aria-label="New conversation">
          <IconPlus size={14} />
          New conversation
        </button>
      </div>

      {/* Conversations */}
      <div className="sidebar-section-label">History</div>
      <nav className="sidebar-conversations" aria-label="Conversations">
        {conversations.length === 0 ? (
          <div style={{ padding: '12px', fontSize: '0.76rem', color: 'var(--text-tertiary)', textAlign: 'center' }}>
            No conversations yet
          </div>
        ) : conversations.map(conv => (
          <div
            key={conv.id}
            className={`conv-item${conv.id === activeId ? ' active' : ''}`}
            onClick={() => onSelect(conv.id)}
            role="button" tabIndex={0}
            aria-current={conv.id === activeId ? 'page' : undefined}
            onKeyDown={e => e.key === 'Enter' && onSelect(conv.id)}
          >
            <div className="conv-item-icon"><IconChat size={14} /></div>
            <div className="conv-item-body">
              <div className="conv-item-title">{conv.title || 'New conversation'}</div>
              <div className="conv-item-date">{formatDate(conv.createdAt)}</div>
            </div>
            <button
              className="conv-item-delete"
              onClick={e => { e.stopPropagation(); onDelete(conv.id) }}
              aria-label="Delete"
            >
              <IconTrash size={12} />
            </button>
          </div>
        ))}
      </nav>

      {/* Documents */}
      {documents.length > 0 && (
        <div className="sidebar-docs">
          <div className="sidebar-docs-label">Documents</div>
          {documents.map(doc => (
            <div key={doc.id} className="doc-item">
              <div className="doc-item-icon">
                {isImageDoc(doc.filename) ? <IconImage size={14} /> : <IconFile size={14} />}
              </div>
              <span
                className={`doc-item-name${activeDocIds.includes(doc.id) ? ' active' : ''}`}
                onClick={() => onToggleDoc(doc.id)}
                title={doc.filename}
              >
                {doc.filename}
              </span>
              {activeDocIds.includes(doc.id) && <span className="doc-active-dot" title="Active" />}
              <button className="doc-remove-btn" onClick={() => onRemoveDoc(doc.id)} aria-label="Remove">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </aside>
  )
}
