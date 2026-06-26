'use client'
import { createContext, useCallback, useContext, useRef, useState } from 'react'
import type { EpisodeSegment } from '@/lib/api'

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

function getSessionId(): string {
  if (typeof window === 'undefined') return ''
  const key = 'paperspod_session'
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}

interface AudioCtxValue {
  episodeId: string | null
  topic: string | null
  playing: boolean
  progress: number             // 0–1
  duration: number             // seconds
  nowOpen: boolean             // NowPlayingOverlay open
  segments: EpisodeSegment[]   // time-coded paper refs (populated after load)
  audioError: string | null    // set when audio fails to load or play
  load: (episodeId: string, audioUrl: string, topic?: string, segments?: EpisodeSegment[]) => void
  togglePlay: () => void
  seek: (pct: number) => void
  toggleNowOpen: () => void
}

const AudioCtx = createContext<AudioCtxValue | null>(null)

export function AudioProvider({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [episodeId, setEpisodeId]   = useState<string | null>(null)
  const [topic, setTopic]           = useState<string | null>(null)
  const [playing, setPlaying]       = useState(false)
  const [progress, setProgress]     = useState(0)
  const [duration, setDuration]     = useState(0)
  const [nowOpen, setNowOpen]       = useState(false)
  const [segments, setSegments]     = useState<EpisodeSegment[]>([])
  const [audioError, setAudioError] = useState<string | null>(null)

  const load = useCallback((eid: string, url: string, t?: string, segs?: EpisodeSegment[]) => {
    const audio = audioRef.current
    if (!audio) return
    if (eid === episodeId) {
      playing ? audio.pause() : audio.play().catch(() => {})
      return
    }
    audio.src = url
    audio.load()
    audio.play().catch(() => {})
    setEpisodeId(eid)
    setTopic(t ?? null)
    setProgress(0)
    setDuration(0)
    setSegments(segs ?? [])
    setAudioError(null)
  }, [episodeId, playing])

  const togglePlay = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    playing ? audio.pause() : audio.play().catch(() => {})
  }, [playing])

  const seek = useCallback((pct: number) => {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    audio.currentTime = pct * audio.duration
  }, [])

  const toggleNowOpen = useCallback(() => setNowOpen(o => !o), [])

  function pct(): number {
    const audio = audioRef.current
    if (!audio || !audio.duration) return 0
    return Math.round((audio.currentTime / audio.duration) * 100)
  }

  function fireEvent(event_type: string, eid: string | null) {
    if (!eid) return
    fetch(`${BASE}/events/play`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        episode_id: eid,
        event_type,
        completion_pct: pct(),
        session_id: getSessionId(),
      }),
    }).catch(() => {})
  }

  function handleTimeUpdate() {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    setProgress(audio.currentTime / audio.duration)
  }

  function handleAudioError(e: React.SyntheticEvent<HTMLAudioElement>) {
    const mediaErr = (e.target as HTMLAudioElement).error
    const msg = mediaErr
      ? ({
          1: 'Playback aborted.',
          2: 'Network error loading audio.',
          3: 'Audio decoding failed.',
          4: 'Audio format not supported.',
        }[mediaErr.code] ?? 'Unknown audio error.')
      : 'Failed to load audio.'
    setPlaying(false)
    setAudioError(msg)
  }

  return (
    <AudioCtx.Provider value={{ episodeId, topic, playing, progress, duration, nowOpen, segments, audioError, load, togglePlay, seek, toggleNowOpen }}>
      {children}
      <audio
        ref={audioRef}
        preload="metadata"
        onPlay={() => { setPlaying(true); fireEvent('play', episodeId) }}
        onPause={() => { setPlaying(false); fireEvent('pause', episodeId) }}
        onTimeUpdate={handleTimeUpdate}
        onDurationChange={() => setDuration(audioRef.current?.duration ?? 0)}
        onEnded={() => { setPlaying(false); setProgress(1); fireEvent('complete', episodeId) }}
        onError={handleAudioError}
      />
    </AudioCtx.Provider>
  )
}

export function useAudio(): AudioCtxValue {
  const ctx = useContext(AudioCtx)
  if (!ctx) throw new Error('useAudio must be used within AudioProvider')
  return ctx
}
