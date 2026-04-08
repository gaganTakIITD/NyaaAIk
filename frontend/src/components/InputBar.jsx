import { useState, useRef, useCallback, useEffect } from 'react'
import UploadModal from './UploadModal.jsx'
import { IconSend, IconAttach, IconFile, IconImage } from '../utils/icons.jsx'
import { useVoiceInput } from '../hooks/useVoiceInput.js'

function isImageDoc(filename = '') {
  return /\.(png|jpg|jpeg|webp|gif)$/i.test(filename)
}

// Mic icon SVG
function MicIcon({ size = 16, recording = false, ...p }) {
  if (recording) {
    // Waveform / stop icon when recording
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" {...p}>
        <rect x="6" y="6" width="12" height="12" rx="2" />
      </svg>
    )
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" {...p}>
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  )
}

export default function InputBar({
  onSend, disabled,
  documents, activeDocIds, onUpload, onRemoveDoc, onToggleDoc, isUploading,
  value, onChange,
}) {
  const [showUpload, setShowUpload] = useState(false)
  const [pasteNotice, setPasteNotice] = useState('')
  const textareaRef = useRef(null)

  // Voice input — transcribed text merges into textarea
  const { isListening, isSupported, interimText, startListening, stopListening, error: voiceError } = useVoiceInput({
    onTranscript: (text) => {
      onChange(text)
    },
    lang: 'en-IN',
  })

  // When interimText arrives, show it as a ghost suffix in the textarea
  const displayValue = isListening && interimText
    ? (value || '') + interimText
    : (value || '')

  // Auto-resize
  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
      if (value && !isListening) ta.focus()
    }
  }, [value, isListening])

  const handleSend = useCallback(() => {
    if (isListening) stopListening()
    const t = (value || '').trim()
    if (!t || disabled) return
    onSend(t)
    onChange('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [value, disabled, onSend, onChange, isListening, stopListening])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }, [handleSend])

  const handleInput = useCallback((e) => {
    onChange(e.target.value)
    const ta = textareaRef.current
    if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 160) + 'px' }
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
        return
      }
    }
  }, [onUpload])

  const toggleMic = useCallback(() => {
    if (isListening) stopListening()
    else startListening()
  }, [isListening, startListening, stopListening])

  const activeDocs = documents.filter(d => activeDocIds.includes(d.id) && d.status === 'ok')
  const hasUploadedDocs = documents.some(d => d.status === 'ok')

  return (
    <div className="input-section">
      {/* Recording banner */}
      {isListening && (
        <div className="voice-banner" role="status" aria-live="polite">
          <span className="voice-banner-dot" aria-hidden="true" />
          <span>Listening — speak your case in English or Hindi-English mix</span>
          {interimText && (
            <span className="voice-interim" aria-live="polite"> &ldquo;{interimText}&rdquo;</span>
          )}
          <button
            className="voice-banner-stop"
            onClick={stopListening}
            aria-label="Stop recording"
          >
            Stop
          </button>
        </div>
      )}

      {/* Voice error */}
      {voiceError && (
        <div style={{
          marginBottom: 6, padding: '5px 12px',
          background: 'var(--error-dim)', border: '1px solid rgba(242,139,130,0.2)',
          borderRadius: 'var(--radius-full)', fontSize: '0.72rem', color: 'var(--error)',
        }}>
          {voiceError}
        </div>
      )}

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

      <div className={`input-wrap${isListening ? ' recording' : ''}`} id="inputContainer">
        <textarea
          ref={textareaRef}
          className="input-textarea"
          id="queryInput"
          placeholder={isListening ? 'Speak now…' : 'Ask a legal question, speak with microphone, or paste a screenshot (Ctrl+V)'}
          value={displayValue}
          onInput={handleInput}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled}
          rows={1}
          aria-label="Legal query"
          aria-describedby={isListening ? 'voiceBanner' : undefined}
        />
        <div className="input-btns">
          {/* Mic button */}
          {isSupported && (
            <button
              className={`mic-btn${isListening ? ' recording' : ''}`}
              onClick={toggleMic}
              title={isListening ? 'Stop recording (click to stop)' : 'Start voice input'}
              aria-label={isListening ? 'Stop recording' : 'Start voice input'}
              id="micBtn"
              disabled={disabled && !isListening}
            >
              <MicIcon size={15} recording={isListening} />
            </button>
          )}

          {/* Attach */}
          <button
            className={`attach-btn${hasUploadedDocs ? ' has-docs' : ''}`}
            onClick={() => setShowUpload(true)}
            title="Upload document or image (or paste screenshot Ctrl+V)"
            aria-label="Upload document"
            id="uploadBtn"
            disabled={isUploading}
          >
            <IconAttach size={15} />
          </button>

          {/* Send */}
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
        <span>
          <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> new line · <kbd>Ctrl+V</kbd> paste image
          {isSupported && ' · Mic for voice'}
        </span>
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
