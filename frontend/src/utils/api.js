// Centralised API helpers — proxied to Flask via Vite dev server

const BASE = ''  // Empty = same origin (works for both dev proxy and prod)

// Safely parse response — returns JSON if possible, otherwise returns the raw text as an error string
async function _safeJson(res) {
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return res.json()
  }
  // Got HTML or plain text — extract useful info
  const text = await res.text()
  // Flask often puts the real error inside <pre> tags in HTML error pages
  const preMatch = text.match(/<pre[^>]*>([\s\S]*?)<\/pre>/i)
  const msg = preMatch ? preMatch[1].trim() : `HTTP ${res.status} — server returned HTML instead of JSON`
  throw new Error(msg)
}

export async function apiChat({ query, court, style, persona, history, docIds }) {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      court:   court   || 'all',
      style:   style   || 'neutral',
      persona: persona || 'advocate',
      history: history || [],
      doc_ids: docIds  || [],
    }),
  })
  if (!res.ok) {
    const data = await _safeJson(res).catch(e => { throw e })
    throw new Error(data?.error || `Server error ${res.status}`)
  }
  return _safeJson(res)
}

export async function apiTopics() {
  const res = await fetch(`${BASE}/api/topics`)
  if (!res.ok) throw new Error('Failed to load topics')
  return _safeJson(res)
}

export async function apiUpload(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/api/upload`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    await _safeJson(res).catch(e => { throw e })
  }
  return _safeJson(res)
}

export async function apiDeleteDoc(docId) {
  const res = await fetch(`${BASE}/api/documents/${docId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('Failed to remove document')
  return _safeJson(res)
}

export async function apiHealth() {
  const res = await fetch(`${BASE}/api/health`)
  return res.ok
}
