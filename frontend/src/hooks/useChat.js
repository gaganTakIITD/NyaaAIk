import { useState, useCallback, useEffect, useRef } from 'react'
import { apiChat } from '../utils/api.js'

const STORAGE_KEY = 'nyaaaik_conversations'
const MAX_HISTORY = 50  // max messages to send as context

function genId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function newConversation() {
  return {
    id: genId(),
    title: 'New Conversation',
    createdAt: Date.now(),
    messages: [],
  }
}

function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveConversations(convs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(convs))
  } catch {
    // localStorage might be full — silently ignore
  }
}

export function useChat() {
  const [conversations, setConversations] = useState(() => {
    const saved = loadConversations()
    if (saved.length === 0) {
      const fresh = newConversation()
      return [fresh]
    }
    return saved
  })
  const [activeId, setActiveId] = useState(() => {
    const saved = loadConversations()
    return saved.length > 0 ? saved[0].id : null
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [court, setCourt] = useState('all')
  const [style, setStyle] = useState('neutral')
  const [persona, setPersona] = useState('advocate')

  // Persist to localStorage whenever conversations change
  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  // Derived: active conversation
  const activeConversation = conversations.find(c => c.id === activeId) || conversations[0] || newConversation()

  // Ensure activeId is always valid
  useEffect(() => {
    if (!conversations.find(c => c.id === activeId) && conversations.length > 0) {
      setActiveId(conversations[0].id)
    }
  }, [conversations, activeId])

  const startNewChat = useCallback(() => {
    const fresh = newConversation()
    setConversations(prev => [fresh, ...prev])
    setActiveId(fresh.id)
    setError(null)
  }, [])

  const selectConversation = useCallback((id) => {
    setActiveId(id)
    setError(null)
  }, [])

  const deleteConversation = useCallback((id) => {
    setConversations(prev => {
      const filtered = prev.filter(c => c.id !== id)
      if (filtered.length === 0) {
        const fresh = newConversation()
        setActiveId(fresh.id)
        return [fresh]
      }
      return filtered
    })
    setActiveId(prev => {
      if (prev === id) {
        const remaining = conversations.filter(c => c.id !== id)
        return remaining.length > 0 ? remaining[0].id : null
      }
      return prev
    })
  }, [conversations])

  const sendMessage = useCallback(async (query, docIds = []) => {
    if (!query.trim() || isLoading) return

    const userMsg = {
      id: genId(),
      role: 'user',
      content: query.trim(),
      timestamp: Date.now(),
    }

    // Add user message and update conversation title on first message
    setConversations(prev => prev.map(c => {
      if (c.id !== activeId) return c
      const isFirst = c.messages.length === 0
      return {
        ...c,
        title: isFirst ? query.trim().slice(0, 60) : c.title,
        messages: [...c.messages, userMsg],
      }
    }))

    setIsLoading(true)
    setError(null)

    const startTime = Date.now()

    try {
      // Build history from current conversation (excluding the msg we just added)
      const currentConv = conversations.find(c => c.id === activeId)
      const existingMessages = currentConv?.messages || []

      // Trim to max history (send last N messages)
      const historySlice = existingMessages.slice(-MAX_HISTORY)
      const history = historySlice.map(m => ({
        role: m.role,
        content: m.content,
      }))

      const result = await apiChat({
        query: query.trim(),
        court,
        style,
        persona,
        history,
        docIds,
      })

      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)

      const botMsg = {
        id: genId(),
        role: 'assistant',
        content: result.answer,
        timestamp: Date.now(),
        elapsed,
        lawSources: result.law_sources || [],
        caseSources: result.case_sources || [],
        disclaimer: result.disclaimer,
      }

      setConversations(prev => prev.map(c => {
        if (c.id !== activeId) return c
        return { ...c, messages: [...c.messages, botMsg] }
      }))
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [activeId, isLoading, court, style, conversations])

  const clearError = useCallback(() => setError(null), [])

  return {
    conversations,
    activeConversation,
    activeId,
    selectConversation,
    startNewChat,
    deleteConversation,
    sendMessage,
    isLoading,
    error,
    clearError,
    court, setCourt,
    style, setStyle,
    persona, setPersona,
  }
}
