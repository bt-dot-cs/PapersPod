'use client'
import EpisodeCover from '@/components/EpisodeCover'
import LevelTag from '@/components/LevelTag'
import { useAudio } from '@/contexts/AudioContext'
import { api, type EpisodeSegment, type FeedbackResult, type LibraryEpisode, type Paper } from '@/lib/api'
import { episodeGradient, heroGradient, levelColor } from '@/lib/episode-utils'
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

type FeedbackType = 'bug' | 'improvement' | 'positive'
const FEEDBACK_TYPES: { type: FeedbackType; label: string; credits: number }[] = [
  { type: 'bug',         label: 'Bug report',   credits: 5 },
  { type: 'improvement', label: 'Improvement',  credits: 3 },
  { type: 'positive',    label: 'Positive',     credits: 2 },
]

function FeedbackWidget({ episodeId, getToken }: {
  episodeId: string
  getToken: () => Promise<string | null>
}) {
  const [selected, setSelected] = useState<FeedbackType | null>(null)
  const [content, setContent]   = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult]     = useState<FeedbackResult | null>(null)
  const [error, setError]       = useState('')

  async function submit() {
    if (!selected || content.trim().length < 10) return
    setSubmitting(true)
    setError('')
    try {
      const token = await getToken()
      if (!token) throw new Error('Sign in to submit feedback')
      const res = await api.submitFeedback({ feedback_type: selected, content: content.trim() }, token)
      setResult(res)
      setContent('')
      setSelected(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ marginTop: '40px', paddingTop: '24px', borderTop: '1px solid rgba(240,225,200,0.06)' }}>
      <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '9.5px', letterSpacing: '1.4px', textTransform: 'uppercase', color: '#9a8c76', marginBottom: '10px' }}>
        Feedback
      </div>
      <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginBottom: '14px' }}>
        Help us improve — earn credits for useful feedback.
      </div>

      {result ? (
        <div style={{ padding: '14px 16px', background: '#1b1611', borderRadius: '10px', border: '1px solid rgba(123,174,143,0.2)' }}>
          <div style={{ fontSize: '13px', color: '#7bae8f', marginBottom: '2px' }}>
            {result.throttled
              ? 'Thanks — feedback received (weekly credit cap reached).'
              : `Thanks! +${result.credits_granted} credit${result.credits_granted !== 1 ? 's' : ''} added. Balance: ${result.new_balance}`}
          </div>
          <button
            onClick={() => setResult(null)}
            style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            Submit more feedback
          </button>
        </div>
      ) : (
        <>
          {/* Type selector */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: selected ? '14px' : 0, flexWrap: 'wrap' }}>
            {FEEDBACK_TYPES.map(({ type, label, credits }) => {
              const active = selected === type
              return (
                <button
                  key={type}
                  onClick={() => setSelected(active ? null : type)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '20px',
                    fontSize: '12.5px',
                    fontFamily: "'IBM Plex Mono', monospace",
                    border: `1px solid ${active ? 'rgba(214,164,78,0.5)' : 'rgba(240,225,200,0.1)'}`,
                    background: active ? 'rgba(214,164,78,0.12)' : 'transparent',
                    color: active ? '#d6a44e' : 'var(--text-secondary)',
                    cursor: 'pointer',
                  }}
                >
                  {label}
                  <span style={{ marginLeft: '6px', opacity: 0.65, fontSize: '11px' }}>+{credits}cr</span>
                </button>
              )
            })}
          </div>

          {/* Content + submit */}
          {selected && (
            <div>
              <textarea
                value={content}
                onChange={e => setContent(e.target.value)}
                placeholder="Describe the bug, suggestion, or what you liked… (min 10 characters)"
                rows={3}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: '#14110d',
                  border: '1px solid rgba(240,225,200,0.1)',
                  borderRadius: '8px',
                  color: '#f3ece0',
                  fontSize: '13px',
                  resize: 'vertical',
                  outline: 'none',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                  marginBottom: '10px',
                }}
              />
              {error && <div style={{ fontSize: '12px', color: '#d4715b', marginBottom: '8px' }}>{error}</div>}
              <button
                onClick={submit}
                disabled={submitting || content.trim().length < 10}
                style={{
                  padding: '8px 18px',
                  borderRadius: '8px',
                  background: content.trim().length >= 10 ? '#d6a44e' : 'rgba(214,164,78,0.2)',
                  color: content.trim().length >= 10 ? '#14110d' : '#9a8c76',
                  fontSize: '13px',
                  fontWeight: 600,
                  border: 'none',
                  cursor: content.trim().length >= 10 && !submitting ? 'pointer' : 'default',
                  opacity: submitting ? 0.5 : 1,
                }}
              >
                {submitting ? 'Sending…' : 'Submit'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
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

  const lc = levelColor(level)

  return (
    <div>
      {/* Hero — full-bleed gradient, no border-radius */}
      <div style={{ background: heroGradient(id), padding: '36px 32px 28px' }}>
        <div style={{ display: 'flex', gap: '26px', alignItems: 'flex-end' }}>
          {/* Album cover */}
          <div
            style={{
              width: '200px',
              height: '200px',
              flex: 'none',
              borderRadius: '14px',
              background: episodeGradient(id, level),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 18px 50px rgba(0,0,0,0.5)',
            }}
          >
            <span
              style={{
                fontFamily: "'Spectral', Georgia, serif",
                fontSize: '80px',
                lineHeight: 1,
                color: 'rgba(255,255,255,0.96)',
                textShadow: '0 3px 18px rgba(0,0,0,0.35)',
              }}
            >
              {(topic ?? id).charAt(0).toUpperCase()}
            </span>
          </div>

          {/* Metadata */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: '11px',
                letterSpacing: '2px',
                color: '#d6c9b0',
                textTransform: 'uppercase',
                marginBottom: '12px',
              }}
            >
              {field ? `${field} · Curated Episode` : 'Curated Episode'}
            </div>
            <h1
              style={{
                fontFamily: "'Spectral', Georgia, serif",
                fontSize: '42px',
                fontWeight: 700,
                lineHeight: 1.08,
                marginBottom: '16px',
                color: '#f3ece0',
              }}
            >
              {topic ?? id}
            </h1>

            {/* Meta row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '13px', color: '#c5b9a4', marginBottom: '18px', flexWrap: 'wrap' }}>
              {level && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '9.5px',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase',
                    color: lc,
                    border: `1px solid ${lc}66`,
                    background: `${lc}1a`,
                    padding: '2px 7px',
                    borderRadius: '5px',
                  }}
                >
                  {level}
                </span>
              )}
              <span>PapersPod</span>
              <span style={{ opacity: 0.4 }}>·</span>
              <span>{new Date(episode.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
              {episode.status === 'done' && audioUrl && (
                <button
                  onClick={handlePlay}
                  style={{
                    width: '56px',
                    height: '56px',
                    borderRadius: '50%',
                    background: '#d6a44e',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    boxShadow: '0 8px 26px rgba(214,164,78,0.38)',
                    border: 'none',
                    flexShrink: 0,
                  }}
                >
                  {isPlaying ? (
                    <span style={{ display: 'flex', gap: '4px' }}>
                      <span style={{ width: '4px', height: '17px', background: '#14110d' }} />
                      <span style={{ width: '4px', height: '17px', background: '#14110d' }} />
                    </span>
                  ) : (
                    <svg width="18" height="20" viewBox="0 0 18 20" fill="none">
                      <path d="M2 1.5L16.5 10 2 18.5V1.5z" fill="#14110d" />
                    </svg>
                  )}
                </button>
              )}

              {episode.is_owner && episode.status === 'done' && (
                <button
                  onClick={toggleShare}
                  disabled={sharing}
                  style={{
                    fontSize: '13px',
                    padding: '8px 18px',
                    borderRadius: '22px',
                    background: episode.shared ? 'rgba(240,225,200,0.1)' : 'transparent',
                    color: '#c5b9a4',
                    border: '1px solid rgba(240,225,200,0.2)',
                    cursor: 'pointer',
                    opacity: sharing ? 0.4 : 1,
                  }}
                >
                  {sharing ? '…' : episode.shared ? 'Shared' : 'Share to library'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Content area */}
      <div style={{ padding: '24px 32px 60px' }}>

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

          <FeedbackWidget episodeId={id} getToken={getToken} />
        </>
      )}
      </div>{/* end content area */}
    </div>
  )
}
