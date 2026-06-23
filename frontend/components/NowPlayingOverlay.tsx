'use client'
import EpisodeCover from '@/components/EpisodeCover'
import { useAudio } from '@/contexts/AudioContext'
import { api, type Paper } from '@/lib/api'
import Link from 'next/link'
import { useEffect, useState } from 'react'

function fmtTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function NowPlayingOverlay() {
  const { episodeId, topic, playing, progress, duration, nowOpen, segments, togglePlay, seek, toggleNowOpen } = useAudio()
  const [papers, setPapers]     = useState<Paper[]>([])
  const [manualIdx, setManualIdx] = useState<number | null>(null)

  useEffect(() => {
    if (!episodeId || !nowOpen) return
    api.getPapers(episodeId).then(setPapers).catch(() => {})
  }, [episodeId, nowOpen])

  useEffect(() => {
    setManualIdx(null)
    setPapers([])
  }, [episodeId])

  // Derive which paper index to show: live sync via segments, or manual override
  const currentTime = progress * duration
  function liveIdx(): number {
    if (segments.length === 0 || papers.length === 0) return 0
    // Find the segment active at currentTime
    for (let i = segments.length - 1; i >= 0; i--) {
      if (currentTime >= segments[i].start && segments[i].paper_refs.length > 0) {
        const arxivId = segments[i].paper_refs[0]
        const paperIdx = papers.findIndex(p => p.arxiv_id === arxivId)
        if (paperIdx >= 0) return paperIdx
      }
    }
    return 0
  }

  const selected = manualIdx ?? liveIdx()

  if (!nowOpen || !episodeId) return null

  const elapsed   = progress * duration
  const remaining = duration - elapsed
  const paper     = papers[selected] ?? null

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: 'var(--bg)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-8 py-4 flex-shrink-0 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
          Now Playing
        </span>
        <button
          onClick={toggleNowOpen}
          aria-label="Close"
          className="text-xl leading-none transition-opacity hover:opacity-60"
          style={{ color: 'var(--text-secondary)' }}
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">

        {/* Left: cover + transport */}
        <div className="flex flex-col items-center justify-center w-1/2 p-12 gap-8">
          <EpisodeCover episodeId={episodeId} topic={topic} size="lg" />

          <div className="text-center max-w-xs">
            <Link
              href={`/episodes/${episodeId}`}
              onClick={toggleNowOpen}
              className="text-xl font-semibold hover:opacity-80 transition-opacity"
              style={{ color: 'var(--text-primary)' }}
            >
              {topic ?? episodeId}
            </Link>
          </div>

          {/* Seek bar */}
          <div className="w-full max-w-xs space-y-1.5">
            <div
              role="slider"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress * 100)}
              aria-label="Seek"
              className="w-full h-1 rounded-full cursor-pointer relative"
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
            <div className="flex justify-between">
              <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{fmtTime(elapsed)}</span>
              <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>-{fmtTime(remaining)}</span>
            </div>
          </div>

          {/* Play/pause */}
          <button
            onClick={togglePlay}
            aria-label={playing ? 'Pause' : 'Play'}
            className="w-14 h-14 rounded-full flex items-center justify-center transition-opacity hover:opacity-80"
            style={{ background: 'var(--text-primary)', color: 'var(--bg)' }}
          >
            {playing ? (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <rect x="2" y="1" width="5" height="14" rx="1.5"/>
                <rect x="9" y="1" width="5" height="14" rx="1.5"/>
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M3 1.5L14 8 3 14.5V1.5z"/>
              </svg>
            )}
          </button>
        </div>

        {/* Divider */}
        <div className="w-px flex-shrink-0" style={{ background: 'var(--border)' }} />

        {/* Right: paper list */}
        <div className="flex flex-col w-1/2 p-12 gap-6 overflow-hidden">
          <div className="flex items-center justify-between flex-shrink-0">
            <p className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
              Papers in This Episode
            </p>
            <div className="flex items-center gap-2">
              {segments.length > 0 && (
                <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(214,164,78,0.15)', color: 'var(--accent)' }}>
                  Live sync
                </span>
              )}
              {manualIdx !== null && (
                <button
                  onClick={() => setManualIdx(null)}
                  className="text-xs transition-opacity hover:opacity-70"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Reset to live
                </button>
              )}
            </div>
          </div>

          {papers.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading papers…</p>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-2 pr-1" style={{ scrollbarWidth: 'thin' }}>
              {papers.map((p, i) => (
                <button
                  key={p.arxiv_id}
                  onClick={() => setManualIdx(i)}
                  className="w-full text-left p-4 rounded-xl transition-colors"
                  style={{
                    background: i === selected ? 'var(--bg-elevated)' : 'var(--bg-card)',
                    border: `1px solid ${i === selected ? 'var(--accent)' : 'transparent'}`,
                  }}
                >
                  <p className="text-sm font-medium leading-snug" style={{ color: 'var(--text-primary)' }}>
                    {p.title}
                  </p>
                  <p className="text-xs mt-1 truncate" style={{ color: 'var(--text-secondary)' }}>
                    {p.authors.slice(0, 2).join(', ')}
                    {p.authors.length > 2 ? ` +${p.authors.length - 2}` : ''}
                    {p.published_date ? ` · ${p.published_date.slice(0, 4)}` : ''}
                  </p>
                </button>
              ))}
            </div>
          )}

          {paper && (
            <div className="flex-shrink-0 border-t pt-5 space-y-3" style={{ borderColor: 'var(--border)' }}>
              {paper.annotation && (
                <p className="text-sm leading-relaxed line-clamp-3" style={{ color: 'var(--text-secondary)' }}>
                  {paper.annotation}
                </p>
              )}
              <Link
                href={`/papers/${encodeURIComponent(paper.arxiv_id)}?from=${episodeId}`}
                onClick={toggleNowOpen}
                className="inline-flex items-center gap-1 text-xs font-medium transition-opacity hover:opacity-70"
                style={{ color: 'var(--accent)' }}
              >
                View paper details →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
