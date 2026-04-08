import { useState, useRef, useCallback, useEffect } from 'react'
import UploadModal from './UploadModal.jsx'
import { IconSend, IconAttach, IconFile, IconImage } from '../utils/icons.jsx'
import { useSarvamVoice, SARVAM_LANGUAGES } from '../hooks/useSarvamVoice.js'

function isImageDoc(filename = '') {
  return /\.(png|jpg|jpeg|webp|gif)$/i.test(filename)
}

function MicIcon({ size = 16, recording = false, ...p }) {
  if (recording) {
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

function SpinnerIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
      style={{ animation: 'spin 0.9s linear infinite' }}>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
    </svg>
  )
}

function formatDuration(s) {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function InputBar({
  onSend, disabled,
  documents, activeDocIds, onUpload, onRemoveDoc, onToggleDoc, isUploading,
  value, onChange,
}) {
  const [showUpload, setShowUpload] = useState(false)
  const [pasteNotice, setPasteNotice] = useState('')
  const [voiceLang, setVoiceLang] = useState('hi-IN')
  const [showLangPicker, setShowLangPicker] = useState(false)
  const textareaRef = useRef(null)

  const { isRecording, isTranscribing, isSupported, duration, error: voiceError, toggleRecording } =
    useSarvamVoice({
      onTranscript: (text) => onChange(prev => (prev ? prev + ' ' + text : text)),
      language: voiceLang,
    })

  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
      if (value && !isRecording) ta.focus()
    }
  }, [value, isRecording])

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
    if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 160) + 'px' }
  }, [onChange])

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

  const currentLang = SARVAM_LANGUAGES.find(l => l.code === voiceLang)
  const activeDocs = documents.filter(d => activeDocIds.includes(d.id) && d.status === 'ok')
  const hasUploadedDocs = documents.some(d => d.status === 'ok')

  return (
    <div className="input-section">
      {/* Sarvam recording banner */}
      {isRecording && (
        <div className="voice-banner" role="status" aria-live="polite">
          <span className="voice-banner-dot" aria-hidden="true" />
          <span>Recording in <strong>{currentLang?.label}</strong> — {formatDuration(duration)}</span>
          <span style={{ flex: 1 }} />
          <button className="voice-banner-stop" onClick={toggleRecording}>Stop</button>
        </div>
      )}

      {/* Transcribing indicator */}
      {isTranscribing && (
        <div className="voice-banner" style={{ borderColor: 'rgba(168,199,250,0.25)', background: 'var(--accent-dim)', color: 'var(--accent)' }} role="status">
          <SpinnerIcon size={13} />
          <span>Sarvam Saaras is transcribing your audio…</span>
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

      <div className={`input-wrap${isRecording ? ' recording' : ''}`} id="inputContainer">
        <textarea
          ref={textareaRef}
          className="input-textarea"
          id="queryInput"
          placeholder={
            isRecording ? `Speak in ${currentLang?.label}…` :
            isTranscribing ? 'Transcribing with Sarvam…' :
            'Ask a legal question, use mic for voice, or paste a screenshot (Ctrl+V)'
          }
          value={value || ''}
          onInput={handleInput}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled || isTranscribing}
          rows={1}
          aria-label="Legal query"
        />
        <div className="input-btns">
          {/* Language picker for voice */}
          {isSupported && (
            <div style={{ position: 'relative' }}>
              <button
                className="lang-btn"
                onClick={() => setShowLangPicker(v => !v)}
                title="Select voice language"
                aria-label="Voice language"
                id="langBtn"
                disabled={isRecording || isTranscribing}
              >
                {currentLang?.code.split('-')[0].toUpperCase()}
              </button>
              {showLangPicker && (
                <div className="lang-dropdown" role="listbox" aria-label="Select voice language">
                  {SARVAM_LANGUAGES.map(l => (
                    <button
                      key={l.code}
                      role="option"
                      aria-selected={l.code === voiceLang}
                      className={`lang-option${l.code === voiceLang ? ' selected' : ''}`}
                      onClick={() => { setVoiceLang(l.code); setShowLangPicker(false) }}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Mic button */}
          {isSupported && (
            <button
              className={`mic-btn${isRecording ? ' recording' : ''}${isTranscribing ? ' transcribing' : ''}`}
              onClick={toggleRecording}
              title={isRecording ? 'Stop recording' : `Record in ${currentLang?.label} (Sarvam)`}
              aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
              id="micBtn"
              disabled={(disabled && !isRecording) || isTranscribing}
            >
              {isTranscribing ? <SpinnerIcon size={14} /> : <MicIcon size={15} recording={isRecording} />}
            </button>
          )}

          {/* Attach */}
          <button
            className={`attach-btn${hasUploadedDocs ? ' has-docs' : ''}`}
            onClick={() => setShowUpload(true)}
            title="Upload document or image (Ctrl+V paste also works)"
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
            disabled={disabled || !(value || '').trim() || isTranscribing}
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
          <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> new line · <kbd>Ctrl+V</kbd> paste
          {isSupported && ' · Mic for Indian voice (Sarvam)'}
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
