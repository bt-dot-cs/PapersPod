'use client'
import { useAuth } from '@clerk/nextjs'
import { useCallback, useEffect, useState } from 'react'
import { api, type Episode, type LibraryEpisode } from '@/lib/api'
import EpisodeCover from '@/components/EpisodeCover'
import LevelTag from '@/components/LevelTag'
import Link from 'next/link'

type Tab = 'community' | 'mine'

function epTopic(ep: Episode): string {
  return (ep.manifest?.parameters?.topic as string | undefined) ?? ep.episode_id
}

function epLevel(ep: Episode): string | undefined {
  return ep.manifest?.parameters?.expertise_level as string | undefined
}

function TableRow({ href, cover, topic, meta, right }: {
  href: string
  cover: React.ReactNode
  topic: string
  meta?: React.ReactNode
  right?: React.ReactNode
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-4 px-4 py-3 rounded-lg transition-colors group"
      style={{ background: 'var(--bg-card)' }}
      onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
      onMouseLeave={e => (e.currentTarget.style.background = 'var(--bg-card)')}
    >
      {cover}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{topic}</p>
        {meta && <div className="flex items-center gap-2 mt-0.5">{meta}</div>}
      </div>
      {right && <div className="flex-shrink-0">{right}</div>}
    </Link>
  )
}

export default function LibraryPage() {
  const { getToken } = useAuth()
  const [tab, setTab]           = useState<Tab>('community')
  const [community, setCommunity] = useState<LibraryEpisode[]>([])
  const [mine, setMine]         = useState<Episode[]>([])
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    api.getLibrary().then(setCommunity).catch(() => {})
  }, [])

  const loadMine = useCallback(async () => {
    setLoading(true)
    try {
      const token = await getToken()
      if (!token) return
      const eps = await api.listEpisodes(token)
      setMine(eps.filter(ep => ep.status === 'done'))
    } catch {
      // non-fatal
    } finally {
      setLoading(false)
    }
  }, [getToken])

  useEffect(() => {
    if (tab === 'mine' && mine.length === 0) loadMine()
  }, [tab, mine.length, loadMine])

  const tabs: { key: Tab; label: string }[] = [
    { key: 'community', label: 'Community' },
    { key: 'mine',      label: 'Mine' },
  ]

  return (
    <div>
      <h1
        className="text-xl font-semibold mb-5"
        style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-spectral), Georgia, serif' }}
      >
        Library
      </h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: 'var(--border)' }}>
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
            style={{
              color: tab === key ? 'var(--text-primary)' : 'var(--text-secondary)',
              borderColor: tab === key ? 'var(--accent)' : 'transparent',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Community */}
      {tab === 'community' && (
        community.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            No shared episodes yet.
          </p>
        ) : (
          <div className="space-y-1.5">
            {community.map(ep => (
              <TableRow
                key={ep.episode_id}
                href={`/episodes/${ep.episode_id}`}
                cover={<EpisodeCover episodeId={ep.episode_id} topic={ep.topic} size="xs" />}
                topic={ep.topic}
                meta={
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {ep.listen_count} {ep.listen_count === 1 ? 'listen' : 'listens'}
                  </span>
                }
                right={
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {new Date(ep.created_at).toLocaleDateString()}
                  </span>
                }
              />
            ))}
          </div>
        )
      )}

      {/* Mine */}
      {tab === 'mine' && (
        loading ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading…</p>
        ) : mine.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            No episodes yet.{' '}
            <Link href="/episodes/new" style={{ color: 'var(--accent)' }}>Create one.</Link>
          </p>
        ) : (
          <div className="space-y-1.5">
            {mine.map(ep => {
              const topic = epTopic(ep)
              const level = epLevel(ep)
              return (
                <TableRow
                  key={ep.episode_id}
                  href={`/episodes/${ep.episode_id}`}
                  cover={<EpisodeCover episodeId={ep.episode_id} topic={topic} level={level} size="xs" />}
                  topic={topic}
                  meta={level ? <LevelTag level={level} /> : undefined}
                  right={
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {new Date(ep.created_at).toLocaleDateString()}
                    </span>
                  }
                />
              )
            })}
          </div>
        )
      )}
    </div>
  )
}
