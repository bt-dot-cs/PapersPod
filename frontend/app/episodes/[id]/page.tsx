'use client'
import EpisodeCover from '@/components/EpisodeCover'
import LevelTag from '@/components/LevelTag'
import { useAudio } from '@/contexts/AudioContext'
import { api, type EpisodeSegment, type LibraryEpisode, type Paper } from '@/lib/api'
import { useAuth } from '@clerk/nextjs'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'

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

function paperRefUrl(paper: Paper, episodeId: string, userId?: string | null): string {
  const identifier = paper.doi ?? paper.arxiv_id
  const sessionId = getSessionId()
  const params = new URLSearchParams({ episode_id: episodeId })
  if (sessionId) params.set('session_id', sessionId)
  if (userId) params.set('user_id', userId)
  return `${BASE}/ref/${identifier}?${params}`
}

function PapersTab({ papers, episodeId, userId }: {
  papers: Paper[]
  episodeId: string
  userId?: string | null
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggle(arxivId: string) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(arxivId) ? next.delete(arxivId) : next.add(arxivId)
      return next
    })
  }

  if (papers.length === 0) {
    return <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No papers indexed yet.</p>
  }

  return (
    <ul className="space-y-2">
      {papers.map(paper => {
        const isOpen = expanded.has(paper.arxiv_id)
        const year   = paper.published_date?.slice(0, 4)
        return (
          <li key={paper.arxiv_id} className="rounded-xl overflow-hidden" style={{ background: 'var(--bg-card)' }}>
            <button
              onClick={() => toggle(paper.arxiv_id)}
              className="w-full text-left px-5 py-4 flex items-start justify-between gap-3 transition-colors hover:opacity-90"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium leading-snug" style={{ color: 'var(--text-primary)' }}>
                  {paper.title}
                </p>
                <p className="text-xs mt-1 truncate" style={{ color: 'var(--text-secondary)' }}>
                  {paper.authors.slice(0, 3).join(', ')}
                  {paper.authors.length > 3 ? ` +${paper.authors.length - 3}` : ''}
                  {year ? ` · ${year}` : ''}
                </p>
              </div>
              <span className="flex-shrink-0 text-lg leading-none mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {isOpen ? '−' : '+'}
              </span>
            </button>

            {isOpen && (
              <div className="px-5 pb-5 space-y-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                {paper.authors.length > 0 && (
                  <p className="text-xs pt-3" style={{ color: 'var(--text-secondary)' }}>
                    {paper.authors.join(', ')}
                  </p>
                )}
                {paper.annotation && (
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                    {paper.annotation}
                  </p>
                )}
                <div className="flex items-center gap-4">
                  <a
                    href={paperRefUrl(paper, episodeId, userId)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-medium transition-opacity hover:opacity-70"
                    style={{ color: 'var(--accent)' }}
                  >
                    Read paper →
                  </a>
                  <Link
                    href={`/papers/${encodeURIComponent(paper.arxiv_id)}?from=${episodeId}`}
                    className="text-xs transition-opacity hover:opacity-70"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    View details
                  </Link>
                </div>
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export default function EpisodePage() {
  const { id } = useParams<{ id: string }>()
  const { getToken, userId } = useAuth()
  const audioCtx = useAudio()

  const [episode, setEpisode]   = useState<ReturnType<typeof epParams> & {
    episode_id: string
    status: string
    created_at: string
    error?: string
    shared: boolean
    is_owner?: boolean
    manifest?: Record<string, unknown>
  } | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [related, setRelated]   = useState<LibraryEpisode[]>([])
  const [papers, setPapers]     = useState<Paper[]>([])
  const [tab, setTab]           = useState<'papers' | 'related'>('papers')
  const [error, setError]       = useState('')
  const [sharing, setSharing]   = useState(false)

  function epParams(manifest?: Record<string, unknown>) {
    const p = manifest?.parameters as Record<string, unknown> | undefined
    return {
      topic: p?.topic as string | undefined,
      level: p?.expertise_level as string | undefined,
      field: (p?.disciplines as string[] | undefined)?.[0],
    }
  }

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const token = await getToken()
        const ep = await api.getEpisode(id, token)
        if (cancelled) return
        setEpisode(ep as typeof episode)

        if (ep.status === 'done' && !audioUrl) {
          try {
            const { url } = await api.getAudioUrl(id)
            if (!cancelled) setAudioUrl(url)
          } catch { /* R2 may not be configured */ }

          try {
            const [rel, paps] = await Promise.all([api.getRelated(id), api.getPapers(id)])
            if (!cancelled) { setRelated(rel); setPapers(paps) }
          } catch { /* non-fatal */ }
        }

        if (ep.status === 'queued' || ep.status === 'running') {
          setTimeout(poll, 5000)
        }
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load episode')
      }
    }

    poll()
    return () => { cancelled = true }
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function toggleShare() {
    if (!episode) return
    setSharing(true)
    try {
      const token = await getToken()
      if (!token) return
      const next = !episode.shared
      await api.shareEpisode(id, next, token)
      setEpisode(prev => prev ? { ...prev, shared: next } : prev)
    } catch { /* silently ignore */ }
    finally { setSharing(false) }
  }

  function handlePlay() {
    if (!audioUrl) return
    const { topic } = epParams(episode?.manifest)
    const segs = (episode?.manifest?.segments ?? []) as EpisodeSegment[]
    audioCtx.load(id, audioUrl, topic, segs)
  }

  if (error) return <p className="text-sm" style={{ color: '#f87171' }}>{error}</p>
  if (!episode) return <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading…</p>

  const { topic, level, field } = epParams(episode.manifest)
  const isPlaying = audioCtx.episodeId === id && audioCtx.playing

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="flex items-start gap-6">
        <EpisodeCover episodeId={id} topic={topic} size="lg" className="flex-shrink-0" />
        <div className="min-w-0 flex-1 pt-2">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            {level && <LevelTag level={level} />}
            {field && (
              <span className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
                {field}
              </span>
            )}
          </div>
          <h1 className="text-2xl font-semibold leading-snug mb-1" style={{ color: 'var(--text-primary)' }}>
            {topic ?? id}
          </h1>
          <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
            {new Date(episode.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
          </p>

          <div className="flex items-center gap-3 flex-wrap">
            {episode.status === 'done' && audioUrl && (
              <button
                onClick={handlePlay}
                className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold transition-opacity hover:opacity-80"
                style={{ background: 'var(--text-primary)', color: 'var(--bg)' }}
              >
                {isPlaying ? (
                  <>
                    <svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor" aria-hidden="true">
                      <rect x="1" y="1" width="3.5" height="10" rx="1"/>
                      <rect x="6.5" y="1" width="3.5" height="10" rx="1"/>
                    </svg>
                    Pause
                  </>
                ) : (
                  <>
                    <svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor" aria-hidden="true">
                      <path d="M2.5 1.5L9.5 6 2.5 10.5V1.5z"/>
                    </svg>
                    Play
                  </>
                )}
              </button>
            )}

            {episode.is_owner && episode.status === 'done' && (
              <button
                onClick={toggleShare}
                disabled={sharing}
                className="text-sm px-4 py-2 rounded-full transition-opacity hover:opacity-80 disabled:opacity-40"
                style={{
                  background: episode.shared ? 'var(--bg-elevated)' : 'transparent',
                  color: episode.shared ? 'var(--text-secondary)' : 'var(--text-secondary)',
                  border: '1px solid var(--border)',
                }}
              >
                {sharing ? '…' : episode.shared ? 'Shared' : 'Share to library'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Status */}
      {(episode.status === 'queued' || episode.status === 'running') && (
        <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
          <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--accent)' }} />
          {episode.status === 'queued' ? 'Waiting in queue…' : 'Generating episode…'}
        </div>
      )}

      {episode.status === 'failed' && episode.error && (
        <div className="rounded-xl p-4" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
          <p className="text-sm" style={{ color: '#f87171' }}>{episode.error}</p>
        </div>
      )}

      {episode.status === 'done' && (
        <>
          {!audioUrl && (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Audio not available (R2 not configured)</p>
          )}

          {/* Tabs */}
          <div>
            <div className="flex gap-1 border-b mb-5" style={{ borderColor: 'var(--border)' }}>
              {(['papers', 'related'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className="px-4 py-2.5 text-sm font-medium capitalize transition-colors border-b-2 -mb-px"
                  style={{
                    color: tab === t ? 'var(--text-primary)' : 'var(--text-secondary)',
                    borderColor: tab === t ? 'var(--accent)' : 'transparent',
                  }}
                >
                  {t === 'papers' ? `Papers${papers.length > 0 ? ` (${papers.length})` : ''}` : 'Related'}
                </button>
              ))}
            </div>

            {tab === 'papers' && (
              <PapersTab papers={papers} episodeId={id} userId={userId} />
            )}

            {tab === 'related' && (
              related.length > 0 ? (
                <ul className="space-y-1.5">
                  {related.map(rel => (
                    <li key={rel.episode_id}>
                      <Link
                        href={`/episodes/${rel.episode_id}`}
                        className="flex items-center justify-between gap-4 p-4 rounded-xl transition-colors hover:opacity-90"
                        style={{ background: 'var(--bg-card)' }}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <EpisodeCover episodeId={rel.episode_id} topic={rel.topic} size="xs" />
                          <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{rel.topic}</span>
                        </div>
                        <span className="flex-shrink-0 text-xs" style={{ color: 'var(--text-muted)' }}>
                          {rel.listen_count} listens
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No related episodes found.</p>
              )
            )}
          </div>
        </>
      )}
    </div>
  )
}
