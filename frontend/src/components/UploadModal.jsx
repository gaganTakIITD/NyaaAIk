import { useRef, useState, useCallback } from 'react'
import { IconUpload, IconFile, IconImage, IconClose } from '../utils/icons.jsx'

const TEXT_TYPES = ['.pdf', '.docx', '.doc', '.txt', '.md']
const IMAGE_TYPES = ['.png', '.jpg', '.jpeg', '.webp']
const ALLOWED = [...TEXT_TYPES, ...IMAGE_TYPES]
const MAX_MB = 10

function isImage(filename = '') { return /\.(png|jpg|jpeg|webp|gif)$/i.test(filename) }
function fmtSize(b) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadModal({ documents, activeDocIds, onUpload, onRemoveDoc, onToggleDoc, onClose }) {
  const [dragOver, setDragOver] = useState(false)
  const [err, setErr] = useState('')
  const inputRef = useRef(null)

  const upload = useCallback(async (file) => {
    setErr('')
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED.includes(ext)) { setErr(`Unsupported format. Allowed: ${ALLOWED.join(', ')}`); return }
    if (file.size > MAX_MB * 1024 * 1024) { setErr(`File too large — max ${MAX_MB} MB`); return }
    try { await onUpload(file) } catch (e) { setErr(e.message || 'Upload failed') }
  }, [onUpload])

  const handleFiles = useCallback((files) => Array.from(files).forEach(f => upload(f)), [upload])
  const handleDrop = useCallback((e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }, [handleFiles])

  return (
    <div className="upload-overlay" onClick={e => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true" aria-label="Upload documents">
      <div className="upload-modal">
        <div className="upload-modal-header">
          <div className="upload-modal-title">Upload documents</div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <IconClose size={14} />
          </button>
        </div>

        {/* Dropzone */}
        <div
          className={`dropzone${dragOver ? ' drag-over' : ''}`}
          onDrop={handleDrop}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          role="button" tabIndex={0}
          aria-label="Drop files here or click to browse"
          onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
        >
          <div className="dropzone-icon">
            <IconUpload size={24} color="var(--text-tertiary)" />
          </div>
          <div className="dropzone-title">Drop files here or click to browse</div>
          <div className="dropzone-sub">
            Maverick will analyze your documents alongside BNS law and live precedents
          </div>
          <div className="dropzone-types" style={{ marginTop: 12 }}>
            <span style={{ fontSize: '0.67rem', color: 'var(--text-tertiary)', marginRight: 4 }}>Text:</span>
            {TEXT_TYPES.map(t => <span key={t} className="type-badge">{t}</span>)}
          </div>
          <div className="dropzone-types" style={{ marginTop: 5 }}>
            <span style={{ fontSize: '0.67rem', color: 'var(--accent)', marginRight: 4 }}>Vision:</span>
            {IMAGE_TYPES.map(t => <span key={t} className="type-badge vision">{t}</span>)}
          </div>
        </div>
        <input ref={inputRef} type="file" accept={ALLOWED.join(',')} multiple onChange={e => handleFiles(e.target.files)} />

        {/* Error */}
        {err && (
          <div style={{ marginTop: 10, padding: '8px 12px', background: 'var(--error-dim)', border: '1px solid rgba(242,139,130,0.2)', borderRadius: 'var(--radius-sm)', fontSize: '0.76rem', color: 'var(--error)' }}>
            {err}
          </div>
        )}

        {/* Uploaded list */}
        {documents.length > 0 && (
          <div className="uploaded-list">
            <div className="uploaded-list-label">Uploaded ({documents.length})</div>
            {documents.map(doc => (
              <div key={doc.id} className="uploaded-item">
                <div className="uploaded-item-icon">
                  {isImage(doc.filename) ? <IconImage size={15} color="var(--accent)" /> : <IconFile size={15} />}
                </div>
                <div className="uploaded-item-body">
                  <div className="uploaded-item-name" title={doc.filename}>{doc.filename}</div>
                  <div className="uploaded-item-info">
                    {fmtSize(doc.size)}
                    {doc.pageCount && ` · ${doc.pageCount} page${doc.pageCount > 1 ? 's' : ''}`}
                    {isImage(doc.filename) && ' · Maverick Vision'}
                  </div>
                </div>
                <div className={`uploaded-status ${doc.status}`}>
                  {doc.status === 'ok' && 'Ready'}
                  {doc.status === 'loading' && 'Processing'}
                  {doc.status === 'error' && 'Error'}
                </div>
                {doc.status === 'ok' && (
                  <button
                    className={`toggle-btn${activeDocIds.includes(doc.id) ? ' on' : ''}`}
                    onClick={() => onToggleDoc(doc.id)}
                  >
                    {activeDocIds.includes(doc.id) ? 'Active' : 'Inactive'}
                  </button>
                )}
                <button className="upload-remove" onClick={() => onRemoveDoc(doc.id)} aria-label="Remove">
                  <IconClose size={13} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="modal-footer">
          Documents are extracted and passed to Maverick as context. Images are sent directly via Maverick's vision API — no OCR required.
        </div>
      </div>
    </div>
  )
}
