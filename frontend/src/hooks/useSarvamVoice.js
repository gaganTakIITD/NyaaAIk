import { useState, useRef, useCallback, useEffect } from 'react'

const SARVAM_LANGUAGES = [
  { code: 'hi-IN', label: 'Hindi' },
  { code: 'en-IN', label: 'English' },
  { code: 'ta-IN', label: 'Tamil' },
  { code: 'te-IN', label: 'Telugu' },
  { code: 'bn-IN', label: 'Bengali' },
  { code: 'mr-IN', label: 'Marathi' },
  { code: 'gu-IN', label: 'Gujarati' },
  { code: 'kn-IN', label: 'Kannada' },
  { code: 'ml-IN', label: 'Malayalam' },
  { code: 'pa-IN', label: 'Punjabi' },
]

export { SARVAM_LANGUAGES }

/**
 * useSarvamVoice — Records audio via MediaRecorder, sends to /api/transcribe,
 * which calls Sarvam Saaras v3 STT. Supports 10 Indian languages.
 *
 * Falls back gracefully if MediaRecorder is not supported.
 */
export function useSarvamVoice({ onTranscript, language = 'hi-IN' } = {}) {
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [error, setError] = useState('')
  const [duration, setDuration] = useState(0)

  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)
  const streamRef = useRef(null)

  const isSupported = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder)

  const startRecording = useCallback(async () => {
    setError('')
    setDuration(0)
    chunksRef.current = []

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
      })
      streamRef.current = stream
    } catch (e) {
      setError('Microphone access denied. Please allow microphone in browser settings.')
      return
    }

    // Pick the best mime type that creates a WAV-compatible container
    const mimeType = [
      'audio/webm;codecs=pcm',
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
    ].find(t => MediaRecorder.isTypeSupported(t)) || ''

    const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    mediaRecorderRef.current = mr

    mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }

    mr.onstop = async () => {
      // Stop tracks
      streamRef.current?.getTracks().forEach(t => t.stop())
      clearInterval(timerRef.current)
      setIsRecording(false)
      setIsTranscribing(true)

      const blob = new Blob(chunksRef.current, { type: mr.mimeType || 'audio/webm' })

      try {
        const formData = new FormData()
        formData.append('audio', blob, 'recording.webm')
        formData.append('language', language)

        const resp = await fetch('/api/transcribe', { method: 'POST', body: formData })
        const data = await resp.json()

        if (resp.status === 503) {
          setError('Sarvam API key is not configured on the server.')
        } else if (!resp.ok) {
          throw new Error(data.error || `Transcription failed (${resp.status})`)
        } else if (data.transcript && data.transcript.trim()) {
          onTranscript?.(data.transcript.trim())
        } else if (data.error) {
          setError(data.error)
        } else {
          setError('No speech detected. Please speak clearly and try again.')
        }
      } catch (e) {
        setError(e.message || 'Transcription failed. Please try again.')
      } finally {
        setIsTranscribing(false)
      }
    }

    mr.onerror = () => {
      setError('Recording error. Please try again.')
      setIsRecording(false)
      clearInterval(timerRef.current)
    }

    mr.start(500) // collect chunks every 500ms
    setIsRecording(true)

    // Timer for recording duration display
    timerRef.current = setInterval(() => setDuration(d => d + 1), 1000)
  }, [language, onTranscript])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    clearInterval(timerRef.current)
  }, [])

  const toggleRecording = useCallback(() => {
    if (isRecording) stopRecording()
    else startRecording()
  }, [isRecording, startRecording, stopRecording])

  // Cleanup on unmount
  useEffect(() => () => {
    mediaRecorderRef.current?.state === 'recording' && mediaRecorderRef.current.stop()
    streamRef.current?.getTracks().forEach(t => t.stop())
    clearInterval(timerRef.current)
  }, [])

  return {
    isRecording,
    isTranscribing,
    isSupported,
    duration,
    error,
    startRecording,
    stopRecording,
    toggleRecording,
  }
}
