import { useState, useRef, useCallback, useEffect } from 'react'

const SUPPORTED = !!(window.SpeechRecognition || window.webkitSpeechRecognition)

/**
 * useVoiceInput — Web Speech API hook
 * Returns { isListening, isSupported, transcript, startListening, stopListening, clearTranscript, error }
 */
export function useVoiceInput({ onTranscript, lang = 'en-IN' } = {}) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interimText, setInterimText] = useState('')
  const [error, setError] = useState('')
  const recognitionRef = useRef(null)
  const finalTextRef = useRef('')

  const buildRecognition = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return null
    const r = new SR()
    r.continuous = true
    r.interimResults = true
    r.lang = lang
    r.maxAlternatives = 1

    r.onstart = () => {
      setIsListening(true)
      setError('')
    }

    r.onresult = (e) => {
      let interim = ''
      let finalAddition = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const text = e.results[i][0].transcript
        if (e.results[i].isFinal) {
          finalAddition += text + ' '
        } else {
          interim += text
        }
      }
      if (finalAddition) {
        finalTextRef.current += finalAddition
        setTranscript(finalTextRef.current)
        onTranscript?.(finalTextRef.current)
      }
      setInterimText(interim)
    }

    r.onerror = (e) => {
      const msgs = {
        'not-allowed': 'Microphone access denied. Please allow microphone in browser settings.',
        'no-speech': 'No speech detected — try again.',
        'network': 'Network error during voice recognition.',
        'audio-capture': 'No microphone found on this device.',
      }
      setError(msgs[e.error] || `Voice error: ${e.error}`)
      setIsListening(false)
    }

    r.onend = () => {
      setIsListening(false)
      setInterimText('')
    }

    return r
  }, [lang, onTranscript])

  const startListening = useCallback(() => {
    if (!SUPPORTED) {
      setError('Voice input is not supported in this browser. Use Chrome or Edge.')
      return
    }
    finalTextRef.current = ''
    setTranscript('')
    setInterimText('')
    setError('')
    const r = buildRecognition()
    if (!r) return
    recognitionRef.current = r
    try { r.start() } catch (e) { setError('Could not start microphone.') }
  }, [buildRecognition])

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop()
    recognitionRef.current = null
    setIsListening(false)
    setInterimText('')
  }, [])

  const clearTranscript = useCallback(() => {
    finalTextRef.current = ''
    setTranscript('')
    setInterimText('')
  }, [])

  // Cleanup on unmount
  useEffect(() => () => recognitionRef.current?.stop(), [])

  return {
    isListening,
    isSupported: SUPPORTED,
    transcript,
    interimText,
    startListening,
    stopListening,
    clearTranscript,
    error,
  }
}
