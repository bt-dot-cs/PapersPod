'use client'
import { api, type CostEvent, type Episode } from '@/lib/api'
import { useAuth } from '@clerk/nextjs'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'

const SOURCES = ['auto', 'arxiv', 'openalex', 'crossref', 'plos', 'springer', 'ieee', 'doaj'] as const
const EXPERTISE = ['novice', 'intermediate', 'expert'] as const
const FOCUS = ['breadth', 'depth'] as const

interface FormState {
  topic: string
  disciplines: string
  expertise: 'novice' | 'intermediate' | 'expert'
  focus_mode: 'breadth' | 'depth'
  max_papers: number
  source: string
  anchor_paper: string
  pub_start: string
  pub_end: string
}

const DEFAULT_FORM: FormState = {
  topic: '',
  disciplines: '',
  expertise: 'intermediate',
  focus_mode: 'breadth',
  max_papers: 5,
  source: 'auto',
  anchor_paper: '',
  pub_start: '2022-01-01',
  pub_end: new Date().toISOString().slice(0, 10),
}

function fmt(n?: number | null, decimals = 4) {
  if (n == null) return '—'
  return `$${n.toFixed(decimals)}`
}

function fmtRuntime(s?: number | null) {
  if (s == null) return '—'
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    queued:  'var(--text-muted)',
    running: 'var(--accent)',
    done:    '#6fcf97',
    failed:  '#eb5757',
  }
  return (
    <span style={{ color: colors[status] ?? 'var(--text-muted)', fontWeight: 600, fontSize: 13 }}>
      {status}
    </span>
  )
}

export default function AdminPage() {
  const { getToken } = useAuth()

  const [form, setForm] = useState<FormState>(DEFAULT_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [activeRun, setActiveRun] = useState<{ episode_id: string; status: string } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [costEvents, setCostEvents] = useState<CostEvent[]>([])
  const [loadingCosts, setLoadingCosts] = useState(true)
  const [costError, setCostError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getToken().then(token => {
      if (!token) { setLoadingCosts(false); return }
      api.getAdminCostEvents(token)
        .then(rows => { if (!cancelled) setCostEvents(rows) })
        .catch(e => { if (!cancelled) setCostError(String(e)) })
        .finally(() => { if (!cancelled) setLoadingCosts(false) })
    })
    return () => { cancelled = true }
  }, [getToken])

  function stopPoll() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  useEffect(() => () => stopPoll(), [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setRunError(null)
    setSubmitting(true)
    try {
      const token = await getToken()
      if (!token) throw new Error('Not signed in')

      const disciplines = form.disciplines.split(',').map(s => s.trim()).filter(Boolean)
      if (disciplines.length === 0) throw new Error('Enter at least one discipline')

      const body = {
        topic: form.topic,
        disciplines,
        focus_mode: form.focus_mode,
        publication_date_range: [form.pub_start, form.pub_end],
        max_papers: form.max_papers,
        source: form.source,
        anchor_paper: form.anchor_paper || null,
        user_profile: {
          expertise: disciplines.map(d => ({ discipline: d, level: form.expertise })),
          default_level: form.expertise,
        },
      }

      const result = await api.createEpisode(body, token)
      setActiveRun({ episode_id: result.episode_id, status: 'queued' })

      pollRef.current = setInterval(async () => {
        try {
          const t = await getToken()
          if (!t) return
          const ep: Episode = await api.getEpisode(result.episode_id, t)
          setActiveRun({ episode_id: ep.episode_id, status: ep.status })
          if (ep.status === 'done' || ep.status === 'failed') {
            stopPoll()
            // Refresh cost log
            api.getAdminCostEvents(t).then(rows => setCostEvents(rows)).catch(() => {})
          }
        } catch { /* ignore poll errors */ }
      }, 5000)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  function field(label: string, children: React.ReactNode) {
    return (
      <div className="flex flex-col gap-1">
        <label style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {label}
        </label>
        {children}
      </div>
    )
  }

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    color: 'var(--text-primary)',
    padding: '6px 10px',
    fontSize: 14,
    outline: 'none',
    width: '100%',
  }

  return (
    <div className="p-8 max-w-5xl mx-auto" style={{ color: 'var(--text-primary)' }}>
      <h1 className="text-xl font-semibold mb-8" style={{ color: 'var(--text-primary)' }}>Admin</h1>

      {/* Run Producer */}
      <section
        className="rounded-xl p-6 mb-10"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <h2 className="text-base font-semibold mb-5">Run Episode</h2>
        <form onSubmit={handleSubmit} className="grid gap-4" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <div style={{ gridColumn: '1 / -1' }}>
            {field('Topic', (
              <input
                style={inputStyle}
                required
                value={form.topic}
                onChange={e => setForm(f => ({ ...f, topic: e.target.value }))}
                placeholder="e.g. measure-theoretic causality"
              />
            ))}
          </div>

          <div style={{ gridColumn: '1 / -1' }}>
            {field('Disciplines (comma-separated)', (
              <input
                style={inputStyle}
                required
                value={form.disciplines}
                onChange={e => setForm(f => ({ ...f, disciplines: e.target.value }))}
                placeholder="e.g. machine learning, statistics"
              />
            ))}
          </div>

          {field('Expertise Level', (
            <select
              style={inputStyle}
              value={form.expertise}
              onChange={e => setForm(f => ({ ...f, expertise: e.target.value as typeof form.expertise }))}
            >
              {EXPERTISE.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          ))}

          {field('Focus Mode', (
            <select
              style={inputStyle}
              value={form.focus_mode}
              onChange={e => setForm(f => ({ ...f, focus_mode: e.target.value as typeof form.focus_mode }))}
            >
              {FOCUS.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          ))}

          {field('Max Papers', (
            <input
              style={inputStyle}
              type="number"
              min={1}
              max={10}
              value={form.max_papers}
              onChange={e => setForm(f => ({ ...f, max_papers: Number(e.target.value) }))}
            />
          ))}

          {field('Source', (
            <select
              style={inputStyle}
              value={form.source}
              onChange={e => setForm(f => ({ ...f, source: e.target.value }))}
            >
              {SOURCES.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          ))}

          {field('Publication Start', (
            <input
              style={inputStyle}
              type="date"
              value={form.pub_start}
              onChange={e => setForm(f => ({ ...f, pub_start: e.target.value }))}
            />
          ))}

          {field('Publication End', (
            <input
              style={inputStyle}
              type="date"
              value={form.pub_end}
              onChange={e => setForm(f => ({ ...f, pub_end: e.target.value }))}
            />
          ))}

          <div style={{ gridColumn: '1 / -1' }}>
            {field('Anchor Paper (optional arXiv ID or DOI)', (
              <input
                style={inputStyle}
                value={form.anchor_paper}
                onChange={e => setForm(f => ({ ...f, anchor_paper: e.target.value }))}
                placeholder="e.g. 2606.00754"
              />
            ))}
          </div>

          <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg px-5 py-2 text-sm font-medium transition-opacity"
              style={{
                background: 'var(--accent)',
                color: '#14110d',
                opacity: submitting ? 0.5 : 1,
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Queueing…' : 'Run Episode'}
            </button>

            {activeRun && (
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {activeRun.episode_id.slice(-8)} — <StatusBadge status={activeRun.status} />
                {activeRun.status === 'done' && (
                  <> — <Link href={`/episodes/${activeRun.episode_id}`} style={{ color: 'var(--accent)' }}>View episode</Link></>
                )}
              </span>
            )}

            {runError && (
              <span className="text-sm" style={{ color: '#eb5757' }}>{runError}</span>
            )}
          </div>
        </form>
      </section>

      {/* Cost Log */}
      <section
        className="rounded-xl p-6"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        <h2 className="text-base font-semibold mb-5">Cost Log</h2>

        {loadingCosts && (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading…</p>
        )}
        {costError && (
          <p className="text-sm" style={{ color: '#eb5757' }}>{costError}</p>
        )}
        {!loadingCosts && !costError && costEvents.length === 0 && (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No runs recorded yet. Cost data appears after the first Fly.io-triggered run completes.</p>
        )}

        {costEvents.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th className="pb-2 pr-4">Date</th>
                  <th className="pb-2 pr-4">Topic</th>
                  <th className="pb-2 pr-4">Expertise</th>
                  <th className="pb-2 pr-4">Papers</th>
                  <th className="pb-2 pr-4">Tokens in/out</th>
                  <th className="pb-2 pr-4">Claude</th>
                  <th className="pb-2 pr-4">TTS</th>
                  <th className="pb-2 pr-4">Total</th>
                  <th className="pb-2 pr-4">Runtime</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {costEvents.map(ev => (
                  <tr
                    key={ev.episode_id}
                    style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                  >
                    <td className="py-2 pr-4 whitespace-nowrap">
                      {ev.created_at ? ev.created_at.slice(0, 10) : '—'}
                    </td>
                    <td className="py-2 pr-4" style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ev.topic ?? '—'}
                    </td>
                    <td className="py-2 pr-4">{ev.expertise_level ?? '—'}</td>
                    <td className="py-2 pr-4">{ev.max_papers ?? '—'}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">
                      {ev.tokens_input != null && ev.tokens_output != null
                        ? `${ev.tokens_input.toLocaleString()} / ${ev.tokens_output.toLocaleString()}`
                        : '—'}
                    </td>
                    <td className="py-2 pr-4">{fmt(ev.cost_claude)}</td>
                    <td className="py-2 pr-4">{fmt(ev.cost_tts)}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--accent)', fontWeight: 600 }}>{fmt(ev.cost_total)}</td>
                    <td className="py-2 pr-4">{fmtRuntime(ev.runtime_seconds)}</td>
                    <td className="py-2">
                      <Link
                        href={`/episodes/${ev.episode_id}`}
                        style={{ color: 'var(--accent)', fontSize: 12 }}
                      >
                        →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
