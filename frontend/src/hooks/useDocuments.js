import { useState, useCallback } from 'react'
import { apiUpload, apiDeleteDoc } from '../utils/api.js'

function getFileIcon(filename) {
  const ext = filename.split('.').pop()?.toLowerCase()
  const icons = { pdf: '📄', docx: '📝', doc: '📝', txt: '📃', md: '📃' }
  return icons[ext] || '📎'
}

export function useDocuments() {
  const [documents, setDocuments] = useState([])  // { id, filename, preview, pageCount, status }
  const [activeDocIds, setActiveDocIds] = useState([])  // Which docs are active for next query
  const [isUploading, setIsUploading] = useState(false)

  const uploadFile = useCallback(async (file) => {
    const tempId = `temp_${Date.now()}`
    const tempDoc = {
      id: tempId,
      filename: file.name,
      icon: getFileIcon(file.name),
      size: file.size,
      status: 'loading',
      preview: '',
      pageCount: null,
    }

    setDocuments(prev => [...prev, tempDoc])
    setIsUploading(true)

    try {
      const result = await apiUpload(file)
      const realDoc = {
        id: result.doc_id,
        filename: result.filename,
        icon: getFileIcon(result.filename),
        size: file.size,
        status: 'ok',
        preview: result.preview || '',
        pageCount: result.page_count,
      }
      setDocuments(prev => prev.map(d => d.id === tempId ? realDoc : d))
      // Auto-activate newly uploaded doc
      setActiveDocIds(prev => [...prev, result.doc_id])
      return realDoc
    } catch (err) {
      setDocuments(prev => prev.map(d =>
        d.id === tempId ? { ...d, status: 'error', error: err.message } : d
      ))
      throw err
    } finally {
      setIsUploading(false)
    }
  }, [])

  const removeDocument = useCallback(async (docId) => {
    setDocuments(prev => prev.filter(d => d.id !== docId))
    setActiveDocIds(prev => prev.filter(id => id !== docId))
    try {
      await apiDeleteDoc(docId)
    } catch {
      // Silently ignore — doc is already removed from UI
    }
  }, [])

  const toggleDocActive = useCallback((docId) => {
    setActiveDocIds(prev =>
      prev.includes(docId)
        ? prev.filter(id => id !== docId)
        : [...prev, docId]
    )
  }, [])

  const clearAll = useCallback(() => {
    documents.forEach(d => {
      if (d.status === 'ok') apiDeleteDoc(d.id).catch(() => {})
    })
    setDocuments([])
    setActiveDocIds([])
  }, [documents])

  return {
    documents,
    activeDocIds,
    isUploading,
    uploadFile,
    removeDocument,
    toggleDocActive,
    clearAll,
  }
}
