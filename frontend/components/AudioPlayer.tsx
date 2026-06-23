'use client'
import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'

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

interface Props {
  episodeId: string
  audioUrl: string
}

export default function AudioPlayer({ episodeId, audioUrl }: Props) {
  const ref = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const sessionId = useRef<string>('')

  useEffect(() => {
    sessionId.current = getSessionId()
  }, [])

  function pct(): number {
    const el = ref.current
    if (!el || !el.duration) return 0
    return Math.round((el.currentTime / el.duration) * 100)
  }

  function fire(event_type: string) {
    api.recordPlayEvent({
      episode_id: episodeId,
      event_type,
      completion_pct: pct(),
      session_id: sessionId.current,
    }).catch(() => {})
  }

  return (
    <div className="bg-gray-900 rounded-xl p-5 space-y-3">
      <audio
        ref={ref}
        src={audioUrl}
        onPlay={() => { setPlaying(true); fire('play') }}
        onPause={() => { setPlaying(false); fire('pause') }}
        onEnded={() => { setPlaying(false); fire('complete') }}
        onTimeUpdate={() => {
          const el = ref.current
          if (el && el.duration) setProgress((el.currentTime / el.duration) * 100)
        }}
        className="hidden"
      />

      <div className="flex items-center gap-3">
        <button
          onClick={() => playing ? ref.current?.pause() : ref.current?.play()}
          className="w-10 h-10 rounded-full bg-indigo-600 hover:bg-indigo-500 flex items-center justify-center transition-colors"
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <rect x="5" y="4" width="3" height="12" rx="1" />
              <rect x="12" y="4" width="3" height="12" rx="1" />
            </svg>
          ) : (
            <svg className="w-4 h-4 ml-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M6.3 2.841A1.5 1.5 0 004 4.11v11.78a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
            </svg>
          )}
        </button>

        <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>

        <span className="text-xs text-gray-400 tabular-nums w-8 text-right">
          {Math.round(progress)}%
        </span>
      </div>
    </div>
  )
}
