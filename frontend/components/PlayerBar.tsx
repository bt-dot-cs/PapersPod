'use client'
import { useAudio } from '@/contexts/AudioContext'
import Link from 'next/link'

function fmtTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function PlayerBar() {
  const { episodeId, topic, playing, progress, duration, audioError, togglePlay, seek, toggleNowOpen } = useAudio()

  if (!episodeId) {
    return (
      <div className="player-bar flex items-center justify-center">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Nothing playing</p>
      </div>
    )
  }

  const elapsed   = progress * duration
  const remaining = duration - elapsed

  return (
    <div className="player-bar flex items-center gap-4 px-6">
      {/* Episode info */}
      <div className="flex items-center gap-3 w-52 min-w-0 flex-shrink-0">
        <div
          className="w-10 h-10 rounded flex-shrink-0 flex items-center justify-center text-sm font-bold select-none"
          style={{ background: 'var(--accent)', color: 'var(--bg)' }}
          aria-hidden="true"
        >
          {(topic ?? episodeId).charAt(0).toUpperCase()}
        </div>
        <Link
          href={`/episodes/${episodeId}`}
          className="text-sm font-medium truncate hover:underline"
          style={{ color: 'var(--text-primary)' }}
        >
          {topic ?? episodeId}
        </Link>
      </div>

      {/* Transport + seek */}
      <div className="flex-1 flex flex-col items-center gap-1.5 min-w-0">
        {audioError && (
          <p className="text-xs" style={{ color: 'var(--error, #e05c5c)' }}>{audioError}</p>
        )}
        <button
          onClick={togglePlay}
          aria-label={playing ? 'Pause' : 'Play'}
          className="w-8 h-8 rounded-full flex items-center justify-center transition-opacity hover:opacity-80"
          style={{ background: 'var(--text-primary)', color: 'var(--bg)' }}
        >
          {playing ? (
            <svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor" aria-hidden="true">
              <rect x="1" y="1" width="3.5" height="10" rx="1"/>
              <rect x="6.5" y="1" width="3.5" height="10" rx="1"/>
            </svg>
          ) : (
            <svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor" aria-hidden="true">
              <path d="M2.5 1.5L9.5 6 2.5 10.5V1.5z"/>
            </svg>
          )}
        </button>

        <div className="flex items-center gap-2 w-full max-w-md">
          <span className="text-xs tabular-nums flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
            {fmtTime(elapsed)}
          </span>
          <div
            role="slider"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            aria-label="Seek"
            className="flex-1 h-1 rounded-full cursor-pointer relative"
            style={{ background: 'var(--border)' }}
            onClick={e => {
              const rect = e.currentTarget.getBoundingClientRect()
              seek((e.clientX - rect.left) / rect.width)
            }}
          >
            <div
              className="absolute inset-y-0 left-0 rounded-full pointer-events-none"
              style={{ width: `${progress * 100}%`, background: 'var(--accent)' }}
            />
          </div>
          <span className="text-xs tabular-nums flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
            -{fmtTime(remaining)}
          </span>
        </div>
      </div>

      {/* Now Playing toggle */}
      <div className="w-52 flex justify-end flex-shrink-0">
        <button
          onClick={toggleNowOpen}
          className="text-xs px-3 py-1.5 rounded-md transition-colors hover:opacity-80"
          style={{ color: 'var(--text-secondary)', background: 'var(--bg-elevated)' }}
        >
          Now Playing
        </button>
      </div>
    </div>
  )
}
