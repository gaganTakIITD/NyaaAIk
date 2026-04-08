// Centralised API helpers — proxied to Flask via Vite dev server

const BASE = ''  // Empty = same origin (works for both dev proxy and prod)

export async function apiChat({ query, court, style, history, docIds }) {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      court: court || 'all',
      style: style || 'neutral',
      history: history || [],
      doc_ids: docIds || [],
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `Server error ${res.status}`)
  }
  return res.json()
}

export async function apiTopics() {
  const res = await fetch(`${BASE}/api/topics`)
  if (!res.ok) throw new Error('Failed to load topics')
  return res.json()
}

export async function apiUpload(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/api/upload`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `Upload error ${res.status}`)
  }
  return res.json()
}

export async function apiDeleteDoc(docId) {
  const res = await fetch(`${BASE}/api/documents/${docId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('Failed to remove document')
  return res.json()
}

export async function apiHealth() {
  const res = await fetch(`${BASE}/api/health`)
  return res.ok
}
