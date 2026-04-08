import { useState, useRef, useCallback } from 'react'
import UploadModal from './UploadModal.jsx'
import { IconSend, IconAttach, IconFile, IconImage } from '../utils/icons.jsx'

function isImageDoc(filename = '') {
  return /\.(png|jpg|jpeg|webp|gif)$/i.test(filename)
}

export default function InputBar({
  onSend, disabled,
  documents, activeDocIds, onUpload, onRemoveDoc, onToggleDoc, isUploading,
}) {
  const [text, setText] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const textareaRef = useRef(null)

  const handleSend = useCallback(() => {
    const t = text.trim()
    if (!t || disabled) return
    onSend(t)
    setText('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [text, disabled, onSend])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }, [handleSend])

  const handleInput = useCallback((e) => {
    setText(e.target.value)
    const ta = textareaRef.current
    if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 130) + 'px' }
  }, [])

  const activeDocs = documents.filter(d => activeDocIds.includes(d.id) && d.status === 'ok')
  const hasUploadedDocs = documents.some(d => d.status === 'ok')

  return (
    <div className="input-section">
      {/* Active doc tags */}
      {activeDocs.length > 0 && (
        <div className="active-docs-row">
          {activeDocs.map(doc => (
            <span key={doc.id} className="active-doc-tag">
              {isImageDoc(doc.filename)
                ? <IconImage size={11} />
                : <IconFile size={11} />}
              {doc.filename.length > 22 ? doc.filename.slice(0, 20) + '…' : doc.filename}
              <button onClick={() => onToggleDoc(doc.id)} aria-label="Remove from context">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="input-wrap" id="inputContainer">
        <textarea
          ref={textareaRef}
          className="input-textarea"
          id="queryInput"
          placeholder="Ask a legal question…"
          value={text}
          onInput={handleInput}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          aria-label="Legal query"
        />
        <div className="input-btns">
          <button
            className={`attach-btn${hasUploadedDocs ? ' has-docs' : ''}`}
            onClick={() => setShowUpload(true)}
            title="Upload document or image"
            aria-label="Upload document"
            id="uploadBtn"
            disabled={isUploading}
          >
            <IconAttach size={15} />
          </button>
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            id="sendBtn"
            title="Send (Enter)"
            aria-label="Send"
          >
            <IconSend size={15} />
          </button>
        </div>
      </div>

      <div className="input-hint">
        <span><kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for new line</span>
        <span>Maverick RAG · BNS + Indian Kanoon</span>
      </div>

      {showUpload && (
        <UploadModal
          documents={documents}
          activeDocIds={activeDocIds}
          onUpload={onUpload}
          onRemoveDoc={onRemoveDoc}
          onToggleDoc={onToggleDoc}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  )
}
