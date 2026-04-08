import { useState, useRef, useCallback, useEffect } from 'react'
import UploadModal from './UploadModal.jsx'
import { IconSend, IconAttach, IconFile, IconImage } from '../utils/icons.jsx'

function isImageDoc(filename = '') {
  return /\.(png|jpg|jpeg|webp|gif)$/i.test(filename)
}

export default function InputBar({
  onSend, disabled,
  documents, activeDocIds, onUpload, onRemoveDoc, onToggleDoc, isUploading,
  // Controlled input value (lifted state from App for pre-fill)
  value, onChange,
}) {
  const [showUpload, setShowUpload] = useState(false)
  const [pasteNotice, setPasteNotice] = useState('')
  const textareaRef = useRef(null)

  // Auto-resize textarea when value changes externally (pre-fill)
  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 130) + 'px'
      if (value) ta.focus()
    }
  }, [value])

  const handleSend = useCallback(() => {
    const t = (value || '').trim()
    if (!t || disabled) return
    onSend(t)
    onChange('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [value, disabled, onSend, onChange])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }, [handleSend])

  const handleInput = useCallback((e) => {
    onChange(e.target.value)
    const ta = textareaRef.current
    if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 130) + 'px' }
  }, [onChange])

  // Ctrl+V paste — intercept image from clipboard
  const handlePaste = useCallback(async (e) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const file = item.getAsFile()
        if (!file) continue
        const ext = item.type.split('/')[1] || 'png'
        const named = new File([file], `screenshot-${Date.now()}.${ext}`, { type: item.type })
        try {
          setPasteNotice('Uploading screenshot…')
          await onUpload(named)
          setPasteNotice('Screenshot attached — Maverick will analyze it')
          setTimeout(() => setPasteNotice(''), 3000)
        } catch {
          setPasteNotice('Screenshot upload failed')
          setTimeout(() => setPasteNotice(''), 3000)
        }
        return // only handle first image
      }
    }
    // No image — let normal text paste proceed
  }, [onUpload])

  const activeDocs = documents.filter(d => activeDocIds.includes(d.id) && d.status === 'ok')
  const hasUploadedDocs = documents.some(d => d.status === 'ok')

  return (
    <div className="input-section">
      {/* Paste notice */}
      {pasteNotice && (
        <div style={{
          marginBottom: 6, padding: '5px 12px',
          background: 'var(--success-dim)', border: '1px solid rgba(129,201,149,0.25)',
          borderRadius: 'var(--radius-full)', fontSize: '0.72rem', color: 'var(--success)',
          display: 'inline-flex', alignItems: 'center', gap: 6,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          {pasteNotice}
        </div>
      )}

      {/* Active doc tags */}
      {activeDocs.length > 0 && (
        <div className="active-docs-row">
          {activeDocs.map(doc => (
            <span key={doc.id} className="active-doc-tag">
              {isImageDoc(doc.filename) ? <IconImage size={11} /> : <IconFile size={11} />}
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
          placeholder="Ask a legal question… or paste a screenshot with Ctrl+V"
          value={value || ''}
          onInput={handleInput}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled}
          rows={1}
          aria-label="Legal query"
        />
        <div className="input-btns">
          <button
            className={`attach-btn${hasUploadedDocs ? ' has-docs' : ''}`}
            onClick={() => setShowUpload(true)}
            title="Upload document or image (or paste screenshot with Ctrl+V)"
            aria-label="Upload document"
            id="uploadBtn"
            disabled={isUploading}
          >
            <IconAttach size={15} />
          </button>
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={disabled || !(value || '').trim()}
            id="sendBtn"
            title="Send (Enter)"
            aria-label="Send"
          >
            <IconSend size={15} />
          </button>
        </div>
      </div>

      <div className="input-hint">
        <span><kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> new line · <kbd>Ctrl+V</kbd> paste screenshot</span>
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
