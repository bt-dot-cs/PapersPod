'use client'
import { api, type Paper } from '@/lib/api'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export default function PaperDetailPage() {
  const params       = useParams<{ id: string }>()
  const searchParams = useSearchParams()
  const arxivId      = decodeURIComponent(params.id)
  const fromEpisode  = searchParams.get('from')

  const [paper, setPaper] = useState<Paper | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!fromEpisode) {
      setError('No episode context provided.')
      return
    }
    api.getPapers(fromEpisode)
      .then(papers => {
        const match = papers.find(p => p.arxiv_id === arxivId)
        if (match) setPaper(match)
        else setError('Paper not found in this episode.')
      })
      .catch(() => setError('Failed to load paper.'))
  }, [arxivId, fromEpisode])

  if (error) {
    return (
      <div className="space-y-4">
        <p className="text-sm" style={{ color: '#f87171' }}>{error}</p>
        {fromEpisode && (
          <Link href={`/episodes/${fromEpisode}`} className="text-sm transition-opacity hover:opacity-70" style={{ color: 'var(--accent)' }}>
            ← Back to episode
          </Link>
        )}
      </div>
    )
  }

  if (!paper) {
    return <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading…</p>
  }

  const year       = paper.published_date?.slice(0, 4)
  const identifier = paper.doi ?? paper.arxiv_id
  const refUrl     = `${BASE}/ref/${identifier}?episode_id=${fromEpisode ?? ''}`

  return (
    <div className="max-w-2xl space-y-8">
      {/* Back link */}
      {fromEpisode && (
        <Link
          href={`/episodes/${fromEpisode}`}
          className="inline-flex items-center gap-1 text-xs transition-opacity hover:opacity-70"
          style={{ color: 'var(--text-secondary)' }}
        >
          ← Back to episode
        </Link>
      )}

      {/* Title + authors */}
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold leading-snug" style={{ color: 'var(--text-primary)' }}>
          {paper.title}
        </h1>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {paper.authors.join(', ')}
          </p>
          {year && (
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}
            >
              {year}
            </span>
          )}
        </div>
      </div>

      {/* CTA */}
      <a
        href={refUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold transition-opacity hover:opacity-80"
        style={{ background: 'var(--accent)', color: 'var(--bg)' }}
      >
        Read paper →
      </a>

      {/* Annotation */}
      {paper.annotation && (
        <section className="space-y-2">
          <h2 className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
            Annotation
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>
            {paper.annotation}
          </p>
        </section>
      )}

      {/* DOI */}
      {paper.doi && (
        <section className="space-y-1">
          <h2 className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
            DOI
          </h2>
          <a
            href={refUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-mono transition-opacity hover:opacity-70"
            style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-ibm-plex-mono)' }}
          >
            {paper.doi}
          </a>
        </section>
      )}

      {/* arXiv ID */}
      <section className="space-y-1">
        <h2 className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
          arXiv ID
        </h2>
        <a
          href={`https://arxiv.org/abs/${paper.arxiv_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-mono transition-opacity hover:opacity-70"
          style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-ibm-plex-mono)' }}
        >
          {paper.arxiv_id}
        </a>
      </section>
    </div>
  )
}
